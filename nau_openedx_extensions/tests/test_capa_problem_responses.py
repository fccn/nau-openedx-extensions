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
    get_find_question_label_factory,
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

    def test_returns_original_result_on_choice_count_mismatch(self):
        """
        If the number of (name, text) tuples returned by the original implementation
        doesn't match the number of <choice> children found (e.g. a future upstream
        change to extract_choices's return shape), don't attempt recovery via zip()
        (which would silently misalign choice text) -- just return the original result.
        """
        element = _parse(
            '<choicegroup>'
            '<choice name="choice_0" correct="false"><div>A</div></choice>'
            '<choice name="choice_1" correct="true"><div>B</div></choice>'
            '</choicegroup>'
        )
        original_result = [('choice_0', None)]  # only one tuple for two <choice> elements
        original_func = Mock(return_value=original_result)
        wrapper = get_extract_choices_factory(original_func)

        result = wrapper(element, i18n=Mock(), text_only=True)

        self.assertEqual(result, original_result)


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

    def test_recovers_correct_text_when_original_result_is_blank_separators_only(self):
        """
        Reproduces a variant of nau-technical#948 seen on pretty-printed/indented OLX
        (e.g. after a Studio export/import round-trip): each `<choice>`'s text is
        nested in a `<div>`, so the original implementation's `text()` xpath only
        picks up whitespace text nodes between/around child elements. Joining those
        blank fragments with ", " produces a *non-empty* string made up solely of
        whitespace and comma separators (e.g. "\n  , \n  "), which must still be
        treated as "no real answer" so the wrapper falls through to recovery instead
        of returning that garbage string.
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
        # Simulates joining whitespace-only text() fragments from a single matched
        # <choice correct="true"> element that has multiple indented child elements.
        original_func = Mock(return_value='\n        , \n        , \n      ')
        wrapper = get_find_correct_answer_text_factory(original_func)

        lcp = Mock()
        lcp.tree = tree
        result = wrapper(lcp, 'p_2_1')

        self.assertEqual(result, 'Right answer.')


class TestFindQuestionLabelFactory(unittest.TestCase):
    """
    Test cases for get_find_question_label_factory / find_question_label_wrapper.

    See nau_openedx_extensions.xblocks.capa_problem_responses for the root
    cause of the "Pergunta" (question) column showing "Questão N" instead of
    the actual question text, a follow-up to fccn/nau-technical#948.
    """

    @staticmethod
    def _make_lcp(tree):
        """
        Build a Mock LoncapaProblem-like object with just enough attributes
        for find_question_label_wrapper: a real lxml tree and an i18n
        gettext that's a no-op passthrough (like the real i18n service
        would be for English source strings).
        """
        lcp = Mock()
        lcp.tree = tree
        lcp.capa_system.i18n.gettext = lambda text: text
        return lcp

    def test_passthrough_when_original_result_is_real_text(self):
        """
        When the original implementation already found real question text
        (not the generic "Question N" default), keep it as-is.
        """
        tree = _parse('<problem><multiplechoiceresponse><choicegroup id="x_2_1"/></multiplechoiceresponse></problem>')
        original_func = Mock(return_value='Real question text')
        wrapper = get_find_question_label_factory(original_func)

        result = wrapper(self._make_lcp(tree), 'x_2_1')

        self.assertEqual(result, 'Real question text')

    def test_recovers_question_nested_inside_response_tag(self):
        """
        Reproduces the actual production bug: Studio's rich-text/per-choice
        feedback editor nests the question prompt *inside* the response tag,
        as a sibling of the choice group, instead of as a sibling of the
        response tag itself. The original implementation only checks the
        latter, so it falls back to a generic "Question N" label; the
        wrapper must recover the real prompt text (including from inline
        rich-text markup like <strong>).
        """
        tree = _parse(
            '<problem><multiplechoiceresponse>'
            '<p><strong>O que e o CienciaVitae?</strong></p>'
            '<choicegroup id="x_2_1">'
            '<choice correct="true"><div>Answer</div></choice>'
            '</choicegroup>'
            '</multiplechoiceresponse></problem>'
        )
        # Simulate the real (buggy) upstream behaviour: falls back to the
        # generic default because it looks one level too high in the tree.
        original_func = Mock(return_value='Question 1')
        wrapper = get_find_question_label_factory(original_func)

        result = wrapper(self._make_lcp(tree), 'x_2_1')

        self.assertEqual(result, 'O que e o CienciaVitae?')

    def test_recovers_question_with_rich_text_markup_in_legacy_layout(self):
        """
        Even for the "legacy" layout the original implementation targets
        (prompt as a sibling of the response tag itself), a prompt authored
        with inline rich-text markup (e.g. <strong>) resolves to None via
        the original's direct `.text` read; the wrapper must recover it via
        recursive text extraction.
        """
        tree = _parse(
            '<problem>'
            '<p><strong>Legacy bold question text</strong></p>'
            '<multiplechoiceresponse>'
            '<choicegroup id="x_2_1">'
            '<choice correct="true"><div>Answer</div></choice>'
            '</choicegroup>'
            '</multiplechoiceresponse></problem>'
        )
        # Simulate the real (buggy) upstream behaviour: None from choice.text.
        original_func = Mock(return_value=None)
        wrapper = get_find_question_label_factory(original_func)

        result = wrapper(self._make_lcp(tree), 'x_2_1')

        self.assertEqual(result, 'Legacy bold question text')

    def test_no_matching_element_falls_back_to_original(self):
        """
        If the answer_id can't be found in the tree at all, don't attempt
        recovery -- just return the original result unmodified.
        """
        tree = _parse('<problem></problem>')
        original_func = Mock(return_value='Question 1')
        wrapper = get_find_question_label_factory(original_func)

        result = wrapper(self._make_lcp(tree), 'missing_id')

        self.assertEqual(result, 'Question 1')

    def test_falls_back_to_original_when_no_recovery_possible(self):
        """
        If neither the answer element's own preceding sibling nor its
        parent's preceding sibling is a usable <p>/<label>, gracefully
        return the original (default) result rather than raising or
        returning an empty value.
        """
        tree = _parse(
            '<problem><multiplechoiceresponse>'
            '<choicegroup id="x_2_1">'
            '<choice correct="true"><div>Answer</div></choice>'
            '</choicegroup>'
            '</multiplechoiceresponse></problem>'
        )
        original_func = Mock(return_value='Question 1')
        wrapper = get_find_question_label_factory(original_func)

        result = wrapper(self._make_lcp(tree), 'x_2_1')

        self.assertEqual(result, 'Question 1')

    def test_skips_description_elements_when_looking_for_label(self):
        """
        A <description> element (feedback text, not the question prompt)
        immediately preceding the answer element must be skipped over so the
        real <p>/<label> further back is still found.
        """
        tree = _parse(
            '<problem><multiplechoiceresponse>'
            '<p>Real question text</p>'
            '<description>Some descriptive text, not the question.</description>'
            '<choicegroup id="x_2_1">'
            '<choice correct="true"><div>Answer</div></choice>'
            '</choicegroup>'
            '</multiplechoiceresponse></problem>'
        )
        original_func = Mock(return_value='Question 1')
        wrapper = get_find_question_label_factory(original_func)

        result = wrapper(self._make_lcp(tree), 'x_2_1')

        self.assertEqual(result, 'Real question text')

    def test_recovers_question_from_div_wrapped_prompt(self):
        """
        Reproduces a real production "matching" problem: a single
        <optionresponse> containing several <optioninput> sub-answers, each
        with its own <div> prompt immediately preceding it (not <p>/<label>).
        The original implementation only recognises <p>/<label>, so it falls
        back to the generic default for every sub-answer; the wrapper must
        also recognise <div> and recover each sub-answer's own prompt.
        """
        tree = _parse(
            '<problem><optionresponse>'
            '<div>Overall instructions, not a specific prompt.</div>'
            '<div>First item prompt</div>'
            '<optioninput id="x_2_1"><option correct="true">A</option></optioninput>'
            '<br/>'
            '<div>Second item prompt</div>'
            '<optioninput id="x_2_2"><option correct="true">B</option></optioninput>'
            '</optionresponse></problem>'
        )
        original_func = Mock(return_value='Question 1')
        wrapper = get_find_question_label_factory(original_func)

        self.assertEqual(wrapper(self._make_lcp(tree), 'x_2_1'), 'First item prompt')
        self.assertEqual(wrapper(self._make_lcp(tree), 'x_2_2'), 'Second item prompt')

    def test_recovers_question_from_div_wrapped_prompt_with_trailing_br(self):
        """
        Same "matching" problem shape as `test_recovers_question_from_div_wrapped_prompt`,
        but with a bare `<br/>` (layout/spacing only, no text) sitting directly
        between the `<div>` prompt and its own `<optioninput>` -- a plausible
        Studio/hand-authored OLX layout that isn't covered by the other test
        (where the `<br/>` only appears *between* sub-answers, not between a
        prompt and its own answer). `<br/>` must be skipped just like
        `<description>`, otherwise the positional lookup lands on the `<br/>`
        itself and silently fails to find the real prompt one element further
        back, falling through to the generic "Question N" default.
        """
        tree = _parse(
            '<problem><optionresponse>'
            '<div>First item prompt</div>'
            '<br/>'
            '<optioninput id="x_2_1"><option correct="true">A</option></optioninput>'
            '</optionresponse></problem>'
        )
        original_func = Mock(return_value='Question 1')
        wrapper = get_find_question_label_factory(original_func)

        result = wrapper(self._make_lcp(tree), 'x_2_1')

        self.assertEqual(result, 'First item prompt')

    def test_recovers_question_from_div_wrapped_prompt_with_hr_and_comment(self):
        """
        Same as the `<br/>` case above, but for the other structural/layout
        noise elements the lookup must also skip: a bare `<hr/>` and an XML
        comment. Both must be skipped just like `<br/>`/`<description>`,
        otherwise the positional lookup lands on one of them (neither a
        valid label nor previously in `SKIP_ELEMS`) and silently falls back
        to the generic "Question N" default.
        """
        tree = _parse(
            '<problem><optionresponse>'
            '<div>First item prompt</div>'
            '<hr/>'
            '<!-- a hand-authored comment -->'
            '<optioninput id="x_2_1"><option correct="true">A</option></optioninput>'
            '</optionresponse></problem>'
        )
        original_func = Mock(return_value='Question 1')
        wrapper = get_find_question_label_factory(original_func)

        result = wrapper(self._make_lcp(tree), 'x_2_1')

        self.assertEqual(result, 'First item prompt')

    def test_ignores_non_prompt_div_for_non_optioninput_answers(self):
        """
        `<div>` recovery is intentionally scoped to `<optioninput>` answers
        only (see `_find_label_element_text`'s `allow_div` docstring): for
        other response types (e.g. MCQ/checkbox), a `<div>` immediately
        preceding the answer element is common for unrelated purposes (an
        image wrapper, a shared/general instructions block, etc.), so it
        must NOT be picked up as the question prompt -- doing so would
        silently substitute incorrect text into the report instead of the
        (at least honest) "Question N" placeholder.
        """
        tree = _parse(
            '<problem><multiplechoiceresponse>'
            '<div>Some unrelated image caption, not a question prompt.</div>'
            '<choicegroup id="x_2_1">'
            '<choice correct="true"><div>Answer</div></choice>'
            '</choicegroup>'
            '</multiplechoiceresponse></problem>'
        )
        original_func = Mock(return_value='Question 1')
        wrapper = get_find_question_label_factory(original_func)

        result = wrapper(self._make_lcp(tree), 'x_2_1')

        self.assertEqual(result, 'Question 1')

    def test_recovers_question_even_with_malformed_answer_id(self):
        """
        The generic-default detection must not depend on `answer_id`
        matching the platform's usual `..._<n>_<m>` format: it's derived
        from a regex over the translated template, not from parsing
        `answer_id` itself, so recovery still works even for an unexpected
        answer_id shape.
        """
        tree = _parse(
            '<problem><multiplechoiceresponse>'
            '<p>What is the real question?</p>'
            '<choicegroup id="not-the-usual-id-format">'
            '<choice correct="true"><div>Answer</div></choice>'
            '</choicegroup>'
            '</multiplechoiceresponse></problem>'
        )
        original_func = Mock(return_value='Question 1')
        wrapper = get_find_question_label_factory(original_func)

        result = wrapper(self._make_lcp(tree), 'not-the-usual-id-format')

        self.assertEqual(result, 'What is the real question?')

    def test_falls_back_gracefully_when_i18n_gettext_raises(self):
        """
        If `capa_system.i18n.gettext` is missing/raises an AttributeError or
        TypeError for some reason (e.g. the i18n service itself being
        unavailable/misconfigured), the wrapper must not propagate the
        exception: it should log a warning and fall back to returning the
        original (non-empty) result unmodified, exactly as if recovery had
        been skipped.
        """
        tree = _parse(
            '<problem><multiplechoiceresponse>'
            '<p>Real question text</p>'
            '<choicegroup id="x_2_1">'
            '<choice correct="true"><div>Answer</div></choice>'
            '</choicegroup>'
            '</multiplechoiceresponse></problem>'
        )
        original_func = Mock(return_value='Question 1')
        wrapper = get_find_question_label_factory(original_func)
        lcp = self._make_lcp(tree)
        lcp.capa_system.i18n.gettext = Mock(side_effect=AttributeError('i18n unavailable'))

        result = wrapper(lcp, 'x_2_1')

        self.assertEqual(result, 'Question 1')
