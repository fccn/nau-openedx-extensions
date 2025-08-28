"""
Django management command for importing enrollment allowed domains from a file.
"""

import logging
import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from nau_openedx_extensions.enrollment_by_domain.models import EnrollmentAllowedDomain, EnrollmentAllowedList

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Import enrollment allowed domains from a text file.

    This command allows bulk import of domains into an EnrollmentAllowedList.
    Each line in the file should contain one domain. Empty lines and lines
    starting with # are ignored.
    """

    help = 'Import enrollment allowed domains from a text file'

    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument(
            'file_path',
            type=str,
            help='Path to the text file containing domains (one per line)'
        )

        parser.add_argument(
            'list_code',
            type=str,
            help='Code for the EnrollmentAllowedList'
        )

        parser.add_argument(
            '--description',
            type=str,
            help='Description for the allowed list',
            default=''
        )

        parser.add_argument(
            '--custom-message',
            type=str,
            help='Custom error message for enrollment blocking',
            default=''
        )

    def handle(self, *args, **options):
        """Execute the command."""
        file_path = options['file_path']
        list_code = options['list_code']
        description = options.get('description', '')
        custom_message = options.get('custom_message', '')

        # Validate file exists
        if not os.path.exists(file_path):
            raise CommandError(f"File not found: {file_path}")

        # Parse domains from file
        try:
            domains_from_file = self._parse_domains_file(file_path)
        except Exception as e:
            raise CommandError(f"Error reading file {file_path}: {e}") from e

        if not domains_from_file:
            raise CommandError("No valid domains found in file")

        # Process the import
        with transaction.atomic():
            result = self._process_import(
                list_code, domains_from_file, description, custom_message
            )

        # Display results
        self._display_results(list_code, result)

    def _parse_domains_file(self, file_path):
        """Parse domains from the input file."""
        domains = set()

        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue

                # Basic domain validation
                if self._is_valid_domain(line):
                    domains.add(line.lower())
                else:
                    self.stdout.write(
                        self.style.WARNING(f"Skipping invalid domain on line {line_num}: {line}")
                    )

        return sorted(domains)

    def _is_valid_domain(self, domain):
        """Basic domain validation."""
        if not domain or len(domain) > 253:
            return False

        # Very basic validation - contains dot and no spaces
        return '.' in domain and ' ' not in domain and not domain.startswith('.') and not domain.endswith('.')

    def _process_import(self, list_code, domains_from_file, description, custom_message):
        """Process the domain import."""

        # Get or create the allowed list
        allowed_list, created = EnrollmentAllowedList.objects.get_or_create(
            code=list_code,
            defaults={
                'description': description or f'Allowed domains for {list_code}',
                'custom_exception_message': custom_message
            }
        )

        # Update custom message if provided and list already exists
        if not created and custom_message:
            allowed_list.custom_exception_message = custom_message
            allowed_list.save()

        # Get current domains in the list
        current_domains = set(
            allowed_list.domains.values_list('domain', flat=True)
        )

        domains_from_file_set = set(domains_from_file)

        # Calculate changes - only additions (no removals)
        domains_to_add = domains_from_file_set - current_domains
        domains_unchanged = current_domains & domains_from_file_set

        # Add new domains
        added_count = 0
        for domain in domains_to_add:
            EnrollmentAllowedDomain.objects.create(
                allowed_list=allowed_list,
                domain=domain
            )
            added_count += 1

        return {
            'created': created,
            'domains_in_file': len(domains_from_file),
            'domains_to_add': len(domains_to_add),
            'domains_unchanged': len(domains_unchanged),
            'added_count': added_count,
            'total_domains': allowed_list.domains.count(),
            'allowed_list': allowed_list
        }

    def _display_results(self, list_code, result):
        """Display the import results."""
        self.stdout.write("=" * 60)
        self.stdout.write(f"IMPORT SUMMARY: {list_code}")
        self.stdout.write("=" * 60)

        if result['created']:
            self.stdout.write(self.style.SUCCESS("Created new allowed list"))
        else:
            self.stdout.write("Found existing allowed list")

        # Statistics
        self.stdout.write("")
        self.stdout.write("Domain Statistics:")
        self.stdout.write(f"Domains in file: {result['domains_in_file']}")
        self.stdout.write(f"Domains to add: {result['domains_to_add']}")
        self.stdout.write(f"Domains unchanged: {result['domains_unchanged']}")
        # Results
        self.stdout.write("")
        if result['added_count'] > 0:
            self.stdout.write("Import completed successfully!")
            self.stdout.write(f"Added: {result['added_count']} domains")
            self.stdout.write(f"Total domains in list: {result['total_domains']}")
        else:
            self.stdout.write("No changes needed")
            self.stdout.write("All domains already in list")
            self.stdout.write(f"Total domains in list: {result['total_domains']}")

        self.stdout.write("=" * 60)
