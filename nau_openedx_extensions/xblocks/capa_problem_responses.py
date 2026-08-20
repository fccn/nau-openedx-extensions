"""
Monkeypatches for the capa "Problem Responses" report generation.

Fixes fccn/nau-technical#948: the "Resposta" (answer) and "Resposta Correta"
(correct answer) columns of the "Problem Responses" report show
"Answer Text Missing" / an empty value for multiple-choice/checkbox problems
whose choices were authored with Studio's newer rich-text / per-choice
feedback problem editor.

Root cause
----------
That editor stores each choice's visible text wrapped inside a child
element, e.g.::

    <choice correct="true">
        <div>Uma plataforma para criar e gerir currículos científicos.</div>
        <choicehint><div>...</div></choicehint>
    </choice>

instead of as a direct text node of ``<choice>``, e.g.::

    <choice correct="true">Some answer text</choice>

``xmodule.capa.inputtypes.ChoiceGroup.extract_choices(..., text_only=True)``
(used by ``LoncapaProblem.find_answer_text``) and
``LoncapaProblem.find_correct_answer_text`` both only ever look at the
``<choice>`` element's direct/immediate text node (``choice.text`` /
``text()`` XPath axis), so they get an empty string for every choice
authored in the newer format, even though the problem renders, grades, and
displays feedback perfectly fine for students (that code path uses
``stringify_children``, which does recurse into child elements).

This module patches both lookups to fall back to a recursive text
extraction (skipping ``<choicehint>``/``<compoundhint>`` feedback children)
whenever the upstream logic returns an empty result, without changing any
other behaviour.

A second, related failure mode affects ``find_correct_answer_text`` only:
its ``', '.join(xml_element.xpath('*[@correct="true"]/text()'))`` can match
multiple *whitespace-only* text nodes when the OLX is pretty-printed/indented
(e.g. after a Studio export/import round-trip), producing a non-empty string
made up solely of whitespace and comma separators instead of an empty one.
See ``_BLANK_JOINED_TEXT_RE`` below for how this is detected and routed
through the same recovery fallback.

Follow-up (still nau-technical#948): the "Pergunta" (question) column shows a
generic "Question N" placeholder instead of the actual question text for the
same problems. This is caused by ``LoncapaProblem.find_question_label``,
which looks for the question prompt (a ``<p>``/``<label>`` element) as the
sibling immediately *preceding the response tag itself*, e.g.::

    <p>What is 2+2?</p>
    <multiplechoiceresponse>
        <choicegroup id="...">...</choicegroup>
    </multiplechoiceresponse>

But Studio's rich-text/per-choice-feedback editor instead nests the prompt
*inside* the response tag, as a sibling of the choice group, e.g.::

    <multiplechoiceresponse>
        <p>What is 2+2?</p>
        <choicegroup id="...">...</choicegroup>
    </multiplechoiceresponse>

so the original lookup walks up one level too many and never finds it,
falling through to the "Question N" default. A second, independent bug
affects even the "expected" (sibling-of-response-tag) layout: the prompt's
text is read via the element's direct ``.text`` node only, so a prompt
authored with any inline rich-text formatting (e.g. ``<p><strong>What is
2+2?</strong></p>``) also resolves to empty/``None`` instead of the actual
text. This module patches ``find_question_label`` to also look for the
prompt as a sibling of the answer element itself (in addition to the
original sibling-of-response-tag lookup), and to extract text recursively
(via ``itertext()``) instead of relying on the direct ``.text`` node, in
both cases falling back to this recovery only when the original lookup
didn't already find real question text.

TODO(nau-technical#948): This is a stopgap fix for an upstream Open edX bug.
Once an upstream fix lands in edx-platform/xblocks-contrib, remove these
monkeypatches.
"""

import logging
import re

log = logging.getLogger(__name__)

# Matches a string containing only whitespace and/or comma separators (i.e. no
# actual answer text), which `find_correct_answer_text`'s original `', '.join(...)`
# can produce when every joined `text()` fragment is itself blank (e.g. when choice
# text is authored across multiple pretty-printed/indented whitespace text nodes).
_BLANK_JOINED_TEXT_RE = re.compile(r'[\s,]*')


def _extract_choice_nested_text(choice_element):
    """
    Recursively extract all visible text nested inside a <choice> element,
    excluding <choicehint>/<compoundhint> children (feedback text shown only
    after answering), to recover choice text authored inside a wrapper
    element such as <div> rather than as a direct text node of <choice>.
    """
    text_parts = []
    for child in choice_element:
        if child.tag in ('choicehint', 'compoundhint'):
            continue
        text_parts.append(''.join(child.itertext()))
    return ''.join(text_parts).strip()


def get_extract_choices_factory(prev_extract_choices_func):
    """
    Factory to create a patched `ChoiceGroup.extract_choices` staticmethod.

    Calls the original implementation first (preserving all its existing
    behaviour, including validation/error handling), and only overrides
    choice text that came back empty when `text_only=True`, by falling back
    to `_extract_choice_nested_text`.
    """

    def extract_choices_wrapper(element, i18n, text_only=False):
        """
        Wrapped version of `ChoiceGroup.extract_choices` that fixes empty
        choice text for `text_only=True` when the choice text is nested
        inside a child element (e.g. `<div>`) instead of being a direct
        text node of `<choice>`.
        """
        choices = prev_extract_choices_func(element, i18n, text_only=text_only)
        if not text_only:
            return choices

        choice_elements = [choice for choice in element if choice.tag == 'choice']
        if len(choices) != len(choice_elements):
            # Upstream's extract_choices should always return one (name, text)
            # tuple per <choice> child; if that shape ever changes, log loudly
            # instead of silently misaligning choice text via zip().
            log.warning(
                'ChoiceGroup.extract_choices returned %d choices but found %d '
                '<choice> elements; skipping div-wrapped text recovery.',
                len(choices), len(choice_elements),
            )
            return choices

        fixed_choices = []
        for (name, text), choice_element in zip(choices, choice_elements):
            if not text or not text.strip():
                text = _extract_choice_nested_text(choice_element)
            fixed_choices.append((name, text))
        return fixed_choices

    return extract_choices_wrapper


def get_find_correct_answer_text_factory(prev_find_correct_answer_text_func):
    """
    Factory to create a patched `LoncapaProblem.find_correct_answer_text` method.

    Calls the original implementation first, and only falls back to a
    recursive text extraction (skipping choicehint/compoundhint) when the
    original result is empty, so behaviour for already-working problems is
    unchanged.
    """

    def find_correct_answer_text_wrapper(self, answer_id):
        """
        Wrapped version of `LoncapaProblem.find_correct_answer_text` that
        fixes an empty result for choices whose text is nested inside a
        child element (e.g. `<div>`) instead of being a direct text node
        of `<choice>`.
        """
        result = prev_find_correct_answer_text_func(self, answer_id)
        if result and not _BLANK_JOINED_TEXT_RE.fullmatch(result):
            return result

        xml_elements = self.tree.xpath('//*[@id=$answer_id]', answer_id=answer_id)
        if not xml_elements:
            return result

        xml_element = xml_elements[0]
        if xml_element.tag == 'optioninput' or xml_element.xpath('@answer'):
            # These cases are already fully handled (and not text-based) by
            # the original implementation; nothing more we can recover here.
            return result

        correct_choices = xml_element.xpath('*[@correct="true"]')
        if not correct_choices:
            return result

        texts = [_extract_choice_nested_text(choice) for choice in correct_choices]
        combined_text = ', '.join(text for text in texts if text)
        return combined_text or result

    return find_correct_answer_text_wrapper


def _find_label_element_text(xml_element):
    """
    Look for a `<p>`/`<label>` element immediately preceding `xml_element`
    (skipping `<description>` elements, which are feedback text rather than
    the question prompt), and return its text extracted recursively (via
    `itertext()`, so inline rich-text markup like `<strong>` doesn't cause
    an empty result), or `None` if no such element/text is found.
    """
    SKIP_ELEMS = ('description',)
    LABEL_ELEMS = ('p', 'label')

    candidate = xml_element.getprevious()
    while candidate is not None and candidate.tag in SKIP_ELEMS:
        candidate = candidate.getprevious()

    if candidate is not None and candidate.tag in LABEL_ELEMS:
        text = ''.join(candidate.itertext()).strip()
        if text:
            return text
    return None


def get_find_question_label_factory(prev_find_question_label_func):
    """
    Factory to create a patched `LoncapaProblem.find_question_label` method.

    Calls the original implementation first, and only falls back to the
    recovery logic below when it returned the generic "Question N" default
    (or nothing at all), so behaviour for already-working problems is
    unchanged.
    """

    def find_question_label_wrapper(self, answer_id):
        """
        Wrapped version of `LoncapaProblem.find_question_label` that fixes
        the question prompt not being found for problems whose choices were
        authored with Studio's rich-text / per-choice feedback editor, which
        nests the prompt (e.g. `<p>...</p>`) *inside* the response tag, as a
        sibling of the answer element, rather than as a sibling of the
        response tag itself (the only location the original implementation
        checks). Also fixes prompts using inline rich-text markup (e.g.
        `<p><strong>...</strong></p>`), which the original implementation
        misses because it only reads the element's direct `.text` node.
        """
        result = prev_find_question_label_func(self, answer_id)

        try:
            # Named to avoid babel's translation-string extraction (which
            # matches on the literal identifier `_`/`gettext`/etc.): this
            # reconstructs the *same* already-translated default that
            # `prev_find_question_label_func` computes internally, purely
            # for sentinel comparison below, so it isn't new user-facing
            # text requiring its own catalog entry in this package.
            gettext_fn = self.capa_system.i18n.gettext
            question_nr = int(answer_id.split('_')[-2]) - 1
            default_label = gettext_fn("Question {}").format(question_nr)
        except (IndexError, ValueError):
            default_label = None

        if result and result != default_label:
            return result

        xml_elements = self.tree.xpath('//*[@id=$answer_id]', answer_id=answer_id)
        if len(xml_elements) != 1:
            return result

        xml_element = xml_elements[0]

        # Studio's rich-text/per-choice-feedback editor nests the question
        # prompt inside the response tag, as a sibling of the answer element
        # itself -- check that location first.
        question_text = _find_label_element_text(xml_element)
        if question_text:
            return question_text

        # Otherwise, re-check the "legacy" layout the original implementation
        # targets (the prompt as a sibling of the parent response tag), using
        # recursive text extraction in case the original only failed due to
        # inline rich-text markup.
        parent = xml_element.getparent()
        if parent is None:
            return result

        question_text = _find_label_element_text(parent)
        return question_text or result

    return find_question_label_wrapper
