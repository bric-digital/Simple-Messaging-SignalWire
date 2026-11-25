# pylint: disable=no-member, line-too-long
# -*- coding: utf-8 -*-

import asyncio
import six

from signalwire.relay import RelayClient

from django.core.management.base import BaseCommand
from django.utils import timezone

from quicksilver.decorators import handle_lock, handle_schedule, add_qs_arguments

class Command(BaseCommand):
    help = 'Test Quicksilver task command.'

    @add_qs_arguments
    def add_arguments(self, parser):
        pass

    @handle_schedule
    @handle_lock
    def handle(self, *args, **options):
        pass
