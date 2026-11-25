# pylint: disable=line-too-long, no-member

from django.db.utils import ProgrammingError

from django.conf import settings
from django.core.checks import Error, Warning, register # pylint: disable=redefined-builtin

@register()
def check_signalwire_settings_defined(app_configs, **kwargs): # pylint: disable=unused-argument
    errors = []

    if ('simple_messaging_switchboard' in settings.INSTALLED_APPS) is False:
        if hasattr(settings, 'SIMPLE_MESSAGING_SIGNALWIRE_PROJECT_ID') is False:
            error = Error('SIMPLE_MESSAGING_SIGNALWIRE_PROJECT_ID parameter not defined', hint='Update configuration to include SIMPLE_MESSAGING_SIGNALWIRE_PROJECT_ID.', obj=None, id='simple_messaging_signalwire.E001')
            errors.append(error)

        if hasattr(settings, 'SIMPLE_MESSAGING_SIGNALWIRE_API_TOKEN') is False:
            error = Error('SIMPLE_MESSAGING_SIGNALWIRE_API_TOKEN parameter not defined', hint='Update configuration to include SIMPLE_MESSAGING_SIGNALWIRE_API_TOKEN.', obj=None, id='simple_messaging_signalwire.E002')
            errors.append(error)

        if hasattr(settings, 'SIMPLE_MESSAGING_SIGNALWIRE_HOST') is False:
            error = Error('SIMPLE_MESSAGING_SIGNALWIRE_HOST parameter not defined', hint='Update configuration to include SIMPLE_MESSAGING_SIGNALWIRE_HOST.', obj=None, id='simple_messaging_signalwire.E003')
            errors.append(error)

        if hasattr(settings, 'SIMPLE_MESSAGING_SIGNALWIRE_PHONE_NUMBER') is False:
            error = Error('SIMPLE_MESSAGING_SIGNALWIRE_PHONE_NUMBER parameter not defined', hint='Update configuration to include SIMPLE_MESSAGING_SIGNALWIRE_PHONE_NUMBER.', obj=None, id='simple_messaging_signalwire.E004')
            errors.append(error)
    else:
        try:
            from simple_messaging_switchboard.models import Channel # pylint: disable=import-outside-toplevel, import-error

            count = Channel.objects.filter(channel_type__package_name='simple_messaging_signalwire').count()

            if count == 0:
                error = Warning('simple_messaging_signalwire is installed alongside simple_messaging_switchboard, but no Channels are defined.', hint='Create Channel or consider removing simple_messaging_signalwire from settings.INSTALLED_APPS', obj=None, id='simple_messaging_signalwire.E004')
                errors.append(error)
        except ProgrammingError:
            pass # Migrations not applied

    return errors


@register()
def check_signalwire_channels_defined(app_configs, **kwargs): # pylint: disable=unused-argument
    errors = []

    if 'simple_messaging_switchboard' in settings.INSTALLED_APPS: # pylint: disable=too-many-nested-blocks
        from simple_messaging_switchboard.models import ChannelType, Channel # pylint: disable=import-outside-toplevel, import-error

        try:
            signalwire_type = ChannelType.objects.filter(package_name='simple_messaging_signalwire').first()

            if signalwire_type is None:
                error = Warning('simple_messaging_signalwire installed, but no corresponding Channel Type exists.', hint='Add Channel Type with the "simple_messaging_signalwire" package type.', obj=None, id='simple_messaging_signalwire.W001')
                errors.append(error)
            else:
                signalwire_channels = Channel.objects.filter(channel_type=signalwire_type)

                if signalwire_channels.count() == 0:
                    error = Warning('simple_messaging_signalwire installed, but no corresponding Channel installed.', hint='Add Channel with the "simple_messaging_signalwire" channel type. Disable if needed.', obj=None, id='simple_messaging_signalwire.W002')
                    errors.append(error)
                else:
                    for signalwire_channel in signalwire_channels:
                        config = signalwire_channel.fetch_configuration()

                        if ('project_id' in config) is False:
                            error = Warning('Channel %s missing project_id parameter.' % signalwire_channel, hint='Add SignalWire project ID as the project_id field.', obj=None, id='simple_messaging_signalwire.W003')
                            errors.append(error)

                        if ('api_token' in config) is False:
                            error = Warning('Channel %s missing api_token parameter.' % signalwire_channel, hint='Add SignalWire API token as the auth_token field.', obj=None, id='simple_messaging_signalwire.W004')
                            errors.append(error)

                        if ('host' in config) is False:
                            error = Warning('Channel %s missing host parameter.' % signalwire_channel, hint='Add SignalWire host / space hostname as the host field.', obj=None, id='simple_messaging_signalwire.W005')
                            errors.append(error)

                        if ('phone_number' in config) is False:
                            error = Warning('Channel %s missing phone_number parameter.' % signalwire_channel, hint='Add SignalWire phone number as the phone_number field.', obj=None, id='simple_messaging_signalwire.W006')
                            errors.append(error)

        except ProgrammingError:
            pass # Migrations not applied

    return errors
