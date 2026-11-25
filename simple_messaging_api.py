# pylint: disable=line-too-long, no-member

import importlib
import json
import logging
import mimetypes
import tempfile
import time

from io import BytesIO

import requests
import phonenumbers

from PIL import Image
from twilio.rest import Client

from django.conf import settings
from django.core import files
from django.core.files.base import File
from django.http import HttpResponse
from django.utils import timezone

from simple_messaging.models import IncomingMessage, IncomingMessageMedia, BlockedSender
from simple_messaging.utils import split_into_bundles

logger = logging.getLogger(__name__) # pylint: disable=invalid-name

def process_outgoing_message(outgoing_message, metadata=None): # pylint: disable=too-many-branches, too-many-locals, too-many-statements
    if metadata is None:
        metadata = {}

    project_id = metadata.get('project_id', None)

    if project_id is None:
        if hasattr(settings, 'SIMPLE_MESSAGING_SIGNALWIRE_PROJECT_ID'):
            project_id = settings.SIMPLE_MESSAGING_SIGNALWIRE_PROJECT_ID
        else:
            return None
    else:
        del metadata['project_id']

    api_token = metadata.get('api_token', None)

    if api_token is None:
        if hasattr(settings, 'SIMPLE_MESSAGING_SIGNALWIRE_API_TOKEN'):
            api_token = settings.SIMPLE_MESSAGING_SIGNALWIRE_API_TOKEN
        else:
            return None
    else:
        del metadata['api_token']

    host = metadata.get('host', None)

    if host is None:
        if hasattr(settings, 'SIMPLE_MESSAGING_SIGNALWIRE_HOST'):
            host = settings.SIMPLE_MESSAGING_SIGNALWIRE_HOST
        else:
            return None
    else:
        del metadata['host']

    phone_number = metadata.get('phone_number', None)

    if phone_number is None:
        if hasattr(settings, 'SIMPLE_MESSAGING_SIGNALWIRE_PHONE_NUMBER'):
            phone_number = settings.SIMPLE_MESSAGING_SIGNALWIRE_PHONE_NUMBER
        else:
            return None
    else:
        del metadata['phone_number']

    if (project_id is not None) and (api_token is not None) and (host is not None) and (phone_number is not None): # pylint: disable=too-many-nested-blocks
        client = RestClient(project=project_id, token=api_token, host=host)

        transmission_metadata = {}

        if outgoing_message.transmission_metadata is not None:
            try:
                transmission_metadata = json.loads(outgoing_message.transmission_metadata)
            except ValueError:
                transmission_metadata = {}

        destination = metadata.get('destination', None)

        if destination is None:
            destination = outgoing_message.current_destination()

        media_urls = []

        for outgoing_file in outgoing_message.media.all().order_by('index'):
            media_url = '%s%s' % (settings.SITE_URL, outgoing_file.content_file.url)

            media_urls.append(media_url)

        sent_body = False

        signalwire_ids = []

        outgoing_message_content = outgoing_message.fetch_message(transmission_metadata).strip()

        while len(media_urls) > 0:
            args = {
                'from_': phone_number,
                'to': destination,
            }

            if sent_body is False:
                args['body'] = outgoing_message_content

                sent_body = True

            message_urls = []

            while (len(media_urls) > 0) and (len(message_urls) < 7): # 7 is a SignalWire limit
                message_urls.append(media_urls.pop(0))

            args['media'] = message_urls
            
            signalwire_message = client.messages.create(**args)  

            signalwire_ids.append(signalwire_message['id'])

        if sent_body is False: # No media
            args = {
                'from_': phone_number,
                'to': destination,
                'body': outgoing_message_content,
            }

            signalwire_message = client.messages.create(**args)  

            signalwire_ids.append(signalwire_message['id'])

        metadata['signalwire_id'] = signalwire_ids

        return metadata

    return None

def simple_messaging_media_enabled(outgoing_message): # pylint: disable=unused-argument
    try:
        return settings.SIMPLE_MESSAGING_MEDIA_ENABLED
    except AttributeError:
        pass

    return True

def process_incoming_request(request): # pylint: disable=too-many-locals, too-many-branches, too-many-statements
    if request.POST.get('MessageSid', None) is None:
        return None

    response = '<?xml version="1.0" encoding="UTF-8" ?><Response>'

    responses = []

    for app in settings.INSTALLED_APPS:
        try:
            response_module = importlib.import_module('.simple_messaging_api', package=app)

            responses.extend(response_module.simple_messaging_response(request.POST))
        except ImportError:
            pass
        except AttributeError:
            pass

    for message in responses:
        response += '<Message>' + message + '</Message>'

    response += '</Response>'

    if request.method == 'POST': # pylint: disable=too-many-nested-blocks
        sender = request.POST['From']

        if BlockedSender.objects.filter(sender=sender).count() > 0:
            response = '<?xml version="1.0" encoding="UTF-8" ?><Response></Response>'

            logging.info('[simple_messaging_twilio] Blocked incoming message from %s.', sender)

            return HttpResponse(response, content_type='text/xml')

        record_responses = True

        for app in settings.INSTALLED_APPS:
            try:
                response_module = importlib.import_module('.simple_messaging_api', package=app)

                record_responses = response_module.simple_messaging_record_response(request.POST)
            except ImportError:
                pass
            except AttributeError:
                pass

        if record_responses:
            now = timezone.now()

            destination = request.POST['To']

            incoming = IncomingMessage(recipient=destination, sender=sender)
            incoming.receive_date = now
            incoming.message = request.POST['Body'].strip()
            incoming.transmission_metadata = json.dumps(dict(request.POST), indent=2)

            incoming.save()

            incoming.encrypt_sender()

            num_media = 0

            media_objects = {}

            if 'NumMedia' in request.POST:
                num_media = int(request.POST['NumMedia'])

                for i in range(0, num_media):
                    media = IncomingMessageMedia(message=incoming)

                    media.content_url = request.POST['MediaUrl' + str(i)]
                    media.content_type = request.POST['MediaContentType' + str(i)]
                    media.index = i

                    media.save()

                    media_response = requests.get(media.content_url, timeout=120)

                    if media_response.status_code != requests.codes.ok:
                        continue

                    filename = media.content_url.split('/')[-1]

                    extension = mimetypes.guess_extension(media.content_type)

                    if extension is not None:
                        if extension == '.jpe':
                            extension = '.jpg'

                        filename += extension

                    file_bytes = BytesIO()
                    file_bytes.write(media_response.content)

                    media.content_file.save(filename, files.File(file_bytes))
                    media.save()

                    media_objects[filename] = {
                        'content': file_bytes.getvalue(),
                        'mime-type': media.content_type
                    }

            for app in settings.INSTALLED_APPS:
                try:
                    response_module = importlib.import_module('.simple_messaging_api', package=app)

                    response_module.process_incoming_message(incoming)
                except ImportError:
                    pass
                except AttributeError:
                    pass

    return HttpResponse(response, content_type='text/xml')

# TODO
def lookup_numbers(phone_numbers): # pylint: disable=too-many-branches
    # TODO: Implement
    
    return []

# TODO
def fetch_sync_messages(since): # pylint: disable=too-many-locals
    messages = []

    for channel in channels:
        pass # TODO: Implement per channel

    return messages

def create_initial_switchboard_channels(): # pylint: disable=invalid-name
    from simple_messaging_switchboard.models import Channel, ChannelType  #pylint: disable=import-outside-toplevel, import-error

    signalwire_type = ChannelType.objects.filter(package_name='simple_messaging_signalwire').first()

    if signalwire_type is None:
        signalwire_type = ChannelType.objects.create(name='SignalWire', package_name='simple_messaging_signalwire')

    signalwire_channel = Channel.objects.filter(channel_type=signalwire_type).first()

    if signalwire_channel is None:
        config = {
            'host': 'CHANGEME.signalwire.com',
            'project_id': 'CHANGEME', # nosec
            'api_token': 'CHANGEME', # nosec
            'phone_number': '+19007202660',
        }

        signalwire_channel = Channel.objects.create(name='SignalWire', identifier='signalwire', channel_type=signalwire_type, is_enabled=False, configuration=json.dumps(config, indent=2))
