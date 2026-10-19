import json

from bs4 import BeautifulSoup
from bs4.element import Comment

from src.ast_managers import prepare_code
from src.coderenderer.html import (
    extract_buttons_from_context,
    prepare_html_context,
    render_static_html,
)
from src.generator.question_html import (
    TEMPLATES_DIR,
    _minify_question_html,
    render_question_html,
)


def test_minification_preserves_token_whitespace_and_escaped_code() -> None:
    html = '''
<!-- template comment -->
<div class="code-line">
    <span class="token whitespace">    </span>
    <span class="token whitespace"> \t </span>
    <span class="token string">"a  b &amp; &lt;!-- code --&gt;"</span>
    <span class="token string">first\n  second</span>
    <button id="answer_42"
            title="a &quot;quote&quot; &amp; b" data-node-id="7">
        <i class="ri-play-fill"></i>
    </button>
</div>
'''

    compact = _minify_question_html(html)
    parsed = BeautifulSoup(compact, "html.parser", preserve_whitespace_tags={"span"})

    assert [token.get_text() for token in parsed.select(".token")] == [
        "    ", " \t ", '"a  b & <!-- code -->"', "first\n  second",
    ]
    assert not parsed.find_all(string=lambda text: isinstance(text, Comment))
    assert compact.startswith('<div class="code-line"><span')
    assert compact.endswith("</button></div>")
    button = parsed.select_one("button")
    assert button is not None
    assert button["title"] == 'a "quote" & b'
    assert button["id"] == "answer_42"
    assert button["data-node-id"] == "7"
    assert len(compact) < len(html)


def test_question_html_is_compact_and_keeps_tokens_and_answer_buttons() -> None:
    code = 'if x < 2:\n    print("a  b & <tag>")  # source comment\n'
    manager = prepare_code(code, "python")
    context = prepare_html_context(manager)
    raw = render_static_html(context, templates_dir=str(TEMPLATES_DIR), snippet_only=True)

    result = render_question_html(manager)
    original = BeautifulSoup(raw, "html.parser", preserve_whitespace_tags={"span"})
    compact = BeautifulSoup(result.text, "html.parser", preserve_whitespace_tags={"span"})

    for selector in (".token", ".line-number"):
        assert [(tag.attrs, tag.get_text()) for tag in compact.select(selector)] == [
            (tag.attrs, tag.get_text()) for tag in original.select(selector)
        ]
    for selector in (".injected-button", ".injected-button i"):
        assert [tag.attrs for tag in compact.select(selector)] == [
            tag.attrs for tag in original.select(selector)
        ]
    assert result.buttons == extract_buttons_from_context(context)
    # Ответы CompPrehension ищет по id='answer_N', N - answerId кнопки.
    assert [tag["id"] for tag in compact.select(".injected-button")] == [
        f"answer_{button['action_id']}" for button in result.buttons
    ]
    assert not compact.select("[onclick], [data-action-id]")
    assert "<!--" not in result.text
    assert "\n" not in result.text
    assert "source comment" in result.text
    assert len(result.text) < len(raw)
    assert len(json.dumps(result.text)) < len(json.dumps(raw))
