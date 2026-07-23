# -*- coding: utf-8 -*-
""" Configuration as explained on tutorial
github.com/edx/edx-platform/tree/master/openedx/core/djangoapps/plugins"""
from __future__ import absolute_import, unicode_literals

from django.apps import AppConfig


class NauOpenEdxConfig(AppConfig):
    """App configuration"""

    name = "nau_openedx_extensions"
    verbose_name = "NAU openedX extensions"
    plugin_app = {
        "url_config": {
            "lms.djangoapp": {
                "namespace": "nau-openedx-extensions",
                "regex": r"^nau-openedx-extensions/",
                "relative_path": "urls",
            },
        },
        "settings_config": {
            "lms.djangoapp": {
                "common": {"relative_path": "settings.common"},
                "production": {"relative_path": "settings.production"},
            },
            "cms.djangoapp": {
                'common': {'relative_path': 'settings.common'},
                'production': {'relative_path': 'settings.production'},
            }
        },
        "view_context_config": {
            "lms.djangoapp": {
                "course_dashboard": "nau_openedx_extensions.multi_dashboard.context_processor.get_multi_dashboard_context"  # lint-amnesty, pylint: disable=line-too-long # noqa
            },
        },
    }

    def ready(self):
        """
        Method to perform actions after apps registry is ended
        """
        # Override the default Video xBlock the _poster private function.
        # Override the class was giving more work because of the html dependencies
        # was being loaded from the new package. So it was more easy just replace the
        # method implementation.
        from xmodule.video_block.video_block import \
            VideoBlock  # pylint: disable=import-error,import-outside-toplevel # noqa

        from nau_openedx_extensions import signals  # pylint: disable=import-outside-toplevel,unused-import # noqa
        from nau_openedx_extensions.xblocks.video_block import \
            get_educast_poster_factory  # pylint: disable=import-outside-toplevel # noqa

        # Replace the method in the original VideoBlock class
        prev_poster_func = VideoBlock._poster  # pylint: disable=protected-access
        VideoBlock._poster = get_educast_poster_factory(prev_poster_func)  # pylint: disable=protected-access

        # Override the default bulk email _get_course_email_context private function
        # to inject custom organization data into email context
        from lms.djangoapps.bulk_email import \
            tasks as bulk_email_tasks  # pylint: disable=import-error,import-outside-toplevel # noqa

        prev_email_context_func = bulk_email_tasks._get_course_email_context  # pylint: disable=protected-access
        from nau_openedx_extensions.utils.bulk_email import \
            get_course_email_context_factory  # pylint: disable=import-outside-toplevel # noqa
        bulk_email_tasks._get_course_email_context = \
            get_course_email_context_factory(prev_email_context_func)  # pylint: disable=protected-access

        # Fix the "Problem Responses" report showing "Answer Text Missing" / an empty
        # correct answer for multiple-choice/checkbox problems whose choices were authored
        # with Studio's rich-text / per-choice feedback editor (see nau-technical#948).
        # TODO(nau-technical#948): remove once fixed upstream in edx-platform/xblocks-contrib.
        from xmodule.capa.capa_problem import \
            LoncapaProblem  # pylint: disable=import-error,import-outside-toplevel # noqa
        from xmodule.capa.inputtypes import \
            ChoiceGroup  # pylint: disable=import-error,import-outside-toplevel # noqa
        from nau_openedx_extensions.xblocks.capa_problem_responses import (  # pylint: disable=import-outside-toplevel # noqa
            get_extract_choices_factory,
            get_find_correct_answer_text_factory,
        )

        prev_extract_choices_func = ChoiceGroup.extract_choices  # pylint: disable=protected-access
        ChoiceGroup.extract_choices = staticmethod(
            get_extract_choices_factory(prev_extract_choices_func)  # pylint: disable=protected-access
        )

        prev_find_correct_answer_text_func = LoncapaProblem.find_correct_answer_text  # pylint: disable=protected-access
        LoncapaProblem.find_correct_answer_text = \
            get_find_correct_answer_text_factory(prev_find_correct_answer_text_func)  # pylint: disable=protected-access
