"""Writers, correction attempts and inspectors share the offline gateway policy."""
import pytest

from storm.ai import llm, navigator, report


@pytest.mark.parametrize('flow', ['report', 'navigator'])
def test_mock_writers_and_corrections_leave_room_for_text(bundle, monkeypatch, flow):
    complete = llm.complete
    requests = []
    corrupted = False

    def track(messages, **kwargs):
        nonlocal corrupted
        requests.append(kwargs)
        result = complete(messages, **kwargs)
        # Exercise the prose correction path as well as normal tool rounds.
        if (kwargs['purpose'] in {'storm-report', 'storm-navigator'}
                and not result['tool_calls'] and not corrupted):
            result['text'] = 'The synthetic book lost $987654321. This is hypothetical.'
            corrupted = True
        assert result['provider'] == 'mock'
        return result

    monkeypatch.setattr(llm, 'complete', track)
    if flow == 'report':
        result = report.write_report(report.facts_from_bundle(bundle))
        assert [request['purpose'] for request in requests] == [
            'storm-report', 'storm-report', 'storm-inspector']
    else:
        result = navigator.ask('Stress USDJPY down 3% in 30 minutes')
        assert [request['purpose'] for request in requests] == [
            'storm-navigator', 'storm-navigator', 'navigator-answer', 'navigator-inspector']
    assert result['verified'] and result['inspector']['verdict'] == 'ok'
    assert all(request['reasoning_effort'] == 'low' for request in requests)
    assert all(request['max_tokens'] == (2048 if 'inspector' in request['purpose'] else 4096)
               for request in requests)
