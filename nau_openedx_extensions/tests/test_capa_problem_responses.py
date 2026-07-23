"""
Test cases for the capa "Problem Responses" report monkeypatches.

See nau_openedx_extensions.xblocks.capa_problem_responses for the root
cause of fccn/nau-technical#948 being fixed here.
"""
import unittest
from unittest.mock import Mock

from lxml import etree

from nau_openedx_extensions.xblocks.capa_problem_responses import (
    get_extract_choices_factory,
    get_find_correct_answer_text_factory,
)


def _parse(xml_string):
    return etree.fromstring(xml_string)


class TestExtractChoicesFactory(unittest.TestCase):
    """
    Test cases for get_extract_choices_factory / extract_choices_wrapper.
    """

    def test_passthrough_when_not_text_only(self):
        """
        When text_only=False the wrapper must return the original result unmodified.
        """
        element = _parse('<choicegroup><choice name="choice_0">Text</choice></choicegroup>')
        original_result = [('choice_0', '<div>Text</div>')]
        original_func = Mock(return_value=original_result)
        wrapper = get_extract_choices_factory(original_func)
        i18n = Mock()

        result = wrapper(element, i18n=i18n, text_only=False)

        self.assertEqual(result, original_result)
        original_func.assert_called_once_with(element, i18n, text_only=False)

    def test_passthrough_when_text_already_present(self):
        """
        When the original implementation already found non-empty text, keep it as-is.
        """
        element = _parse('<choicegroup><choice name="choice_0">Plain text</choice></choicegroup>')
        original_func = Mock(return_value=[('choice_0', 'Plain text')])
        wrapper = get_extract_choices_factory(original_func)

        result = wrapper(element, i18n=Mock(), text_only=True)

        self.assertEqual(result, [('choice_0', 'Plain text')])

    def test_recovers_text_nested_in_div(self):
        """
        Reproduces the nau-technical#948 bug: choice text wrapped in <div>, with a
        <choicehint><div>...</div></choicehint> sibling, must resolve to just the
        answer text (not the hint text, and not empty).
        """
        element = _parse(
            '<choicegroup>'
            '<choice name="choice_0" correct="false">'
            '<div>Uma plataforma de bolsa de doutoramento.</div>'
            '<choicehint><div>Hint text that must not leak into the answer.</div></choicehint>'
            '</choice>'
            '<choice name="choice_1" correct="true">'
            '<div>Uma plataforma para criar e gerir curriculos cientificos.</div>'
            '<choicehint><div>Another hint.</div></choicehint>'
            '</choice>'
            '</choicegroup>'
        )
        # Simulate the real (buggy) upstream behaviour: choice.text is None for both.
        original_func = Mock(return_value=[('choice_0', None), ('choice_1', None)])
        wrapper = get_extract_choices_factory(original_func)

        result = wrapper(element, i18n=Mock(), text_only=True)

        self.assertEqual(result, [
            ('choice_0', 'Uma plataforma de bolsa de doutoramento.'),
            ('choice_1', 'Uma plataforma para criar e gerir curriculos cientificos.'),
        ])

    def test_leaves_empty_when_no_nested_text_available(self):
        """
        If there really is no text anywhere (edge case), gracefully returns empty string
        rather than raising.
        """
        element = _parse('<choicegroup><choice name="choice_0" correct="false"></choice></choicegroup>')
        original_func = Mock(return_value=[('choice_0', None)])
        wrapper = get_extract_choices_factory(original_func)

        result = wrapper(element, i18n=Mock(), text_only=True)

        self.assertEqual(result, [('choice_0', '')])


class TestFindCorrectAnswerTextFactory(unittest.TestCase):
    """
    Test cases for get_find_correct_answer_text_factory / find_correct_answer_text_wrapper.
    """

    def test_passthrough_when_original_result_present(self):
        """
        When the original implementation already found a result, keep it as-is.
        """
        original_func = Mock(return_value='Some Answer')
        wrapper = get_find_correct_answer_text_factory(original_func)

        lcp = Mock()
        result = wrapper(lcp, 'some_answer_id')

        self.assertEqual(result, 'Some Answer')

    def test_recovers_correct_text_nested_in_div(self):
        """
        Reproduces the nau-technical#948 bug for `Resposta Correta`: the correct
        <choice>'s text is nested in a <div>, so the plain `text()` xpath used by the
        original implementation returns nothing; the wrapper must recover it while
        excluding <choicehint> content.
        """
        tree = _parse(
            '<problem>'
            '<multiplechoiceresponse id="p_1">'
            '<choicegroup id="p_2_1">'
            '<choice name="choice_0" correct="false">'
            '<div>Wrong answer.</div>'
            '<choicehint><div>Wrong hint.</div></choicehint>'
            '</choice>'
            '<choice name="choice_1" correct="true">'
            '<div>Right answer.</div>'
            '<choicehint><div>Right hint.</div></choicehint>'
            '</choice>'
            '</choicegroup>'
            '</multiplechoiceresponse>'
            '</problem>'
        )
        original_func = Mock(return_value='')
        wrapper = get_find_correct_answer_text_factory(original_func)

        lcp = Mock()
        lcp.tree = tree
        result = wrapper(lcp, 'p_2_1')

        self.assertEqual(result, 'Right answer.')

    def test_no_matching_element_falls_back_to_original(self):
        """
        If the answer_id can't be found in the tree at all, don't attempt recovery.
        """
        tree = _parse('<problem></problem>')
        original_func = Mock(return_value='')
        wrapper = get_find_correct_answer_text_factory(original_func)

        lcp = Mock()
        lcp.tree = tree
        result = wrapper(lcp, 'missing_id')

        self.assertEqual(result, '')

    def test_optioninput_falls_back_to_original(self):
        """
        optioninput-based problems are already fully handled by the original
        implementation and must not be touched by the recovery logic.
        """
        tree = _parse('<problem><optioninput id="p_2_1" correct="Yes"/></problem>')
        original_func = Mock(return_value='')
        wrapper = get_find_correct_answer_text_factory(original_func)

        lcp = Mock()
        lcp.tree = tree
        result = wrapper(lcp, 'p_2_1')

        self.assertEqual(result, '')
