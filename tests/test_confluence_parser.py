from agentkit.integrations.confluence_markdown import storage_to_markdown

SAMPLE = """
<h2>Rollout plan</h2>
<ul><li><p>alpha</p></li><li><p>beta</p></li></ul>
<table><tbody><tr><th>env</th><th>owner</th></tr><tr><td>prod</td><td>ana</td></tr></tbody></table>
<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">python</ac:parameter><ac:plain-text-body>print("hi")</ac:plain-text-body></ac:structured-macro>
<ac:structured-macro ac:name="info"><ac:rich-text-body><p>Freeze starts Friday.</p></ac:rich-text-body></ac:structured-macro>
<p>See <ac:link><ri:page ri:content-title="Runbook"/><ac:plain-text-link-body>the runbook</ac:plain-text-link-body></ac:link>.</p>
<ac:image><ri:attachment ri:filename="diag.png"/></ac:image>
"""

def test_headings_lists_tables():
    out = storage_to_markdown(SAMPLE)
    assert '## Rollout plan' in out
    assert '- alpha' in out and '- beta' in out
    assert '|' in out and 'prod' in out and 'ana' in out

def test_code_macro_becomes_fenced_block():
    out = storage_to_markdown(SAMPLE)
    assert "```python" in out
    assert 'print("hi")' in out

def test_info_panel_becomes_blockquote():
    out = storage_to_markdown(SAMPLE)
    assert '> **Note:**' in out
    assert 'Freeze starts Friday.' in out

def test_links_and_images():
    out = storage_to_markdown(SAMPLE)
    assert 'the runbook](#Runbook)' in out
    assert '![image](diag.png)' in out

def test_empty_input():
    assert storage_to_markdown('') == '\n'