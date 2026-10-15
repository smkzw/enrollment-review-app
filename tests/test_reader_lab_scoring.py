from scripts.score_reader_lab_values import score
import json
import hashlib


def test_numeric_slice_preserves_wrong_missing_and_unreadable():
    gold = {'source_sha256': 'x', 'values': [['WBC', '4.04', ['白细胞计数']]]}
    record = {'page_image_sha256': 'x', 'facts': []}
    assert score(record, gold)[0]['state'] == 'missing_or_unmapped'
    fact = {'field_name': '★白细胞计数', 'raw_value': '4.04 10^9/L', 'observation_id': 'a'}
    record['facts'] = [fact]
    assert score(record, gold)[0]['state'] == 'numeric_match'
    fact['raw_value'] = '4.041 10^9/L'
    assert score(record, gold)[0]['state'] == 'numeric_mismatch'
    fact['raw_value'] = '无法辨认，参考4.04'
    assert score(record, gold)[0]['state'] == 'unreadable_or_unparsed'
    fact['raw_value'] = '4.04-9.0'
    assert score(record, gold)[0]['state'] == 'unreadable_or_unparsed'
    record['facts'].append(dict(fact, observation_id='b'))
    assert score(record, gold)[0]['state'] == 'ambiguous'


def test_batch_scoring_selects_exact_source_and_keeps_run_identity(tmp_path, monkeypatch):
    from scripts.score_reader_lab_values import main
    gold = {'source_sha256': 'x', 'scope': 'numeric only', 'values': [['WBC', '4.04', []]]}
    (tmp_path / 'gold-sar-lab-page9.json').write_text(json.dumps(gold))
    run = tmp_path / 'product-runs-batch-v2' / 'candidate'
    run.mkdir(parents=True)
    (run / 'batch.json').write_text(json.dumps({'records': [
        {'page_artifact_id': 'target', 'page_image_sha256': 'x', 'facts': []},
        {'page_artifact_id': 'other', 'page_image_sha256': 'y', 'facts': []},
    ]}))
    monkeypatch.setattr('sys.argv', ['score', str(tmp_path)])
    main()
    result = json.loads((tmp_path / 'sar-lab-numeric-slice.json').read_text())
    assert len(result['results']) == 1
    assert result['results'][0]['run'] == 'product-runs-batch-v2/candidate/target'
    assert result['results'][0]['counts']['missing_or_unmapped'] == 1
    assert result['clinical_acceptance'] is False


def test_raw_diagnostic_does_not_promote_rejected_record(tmp_path, monkeypatch):
    from scripts.score_reader_lab_values import main
    frozen = tmp_path / 'frozen'
    frozen.mkdir()
    content = json.dumps({'pages': [{'page_image_sha256': 'x'}]})
    (frozen / 'input.json').write_text(content)
    manifest = json.dumps({'files': {'input.json': hashlib.sha256(content.encode()).hexdigest()}})
    (frozen / 'manifest.json').write_text(manifest)
    (tmp_path / 'gold-sar-lab-page9.json').write_text(json.dumps({
        'source_sha256': 'x', 'scope': 'numeric only', 'values': [['WBC', '4.04', []]]}))
    run = tmp_path / 'product-runs-test' / 'sample-page-0'
    run.mkdir(parents=True)
    (run / 'run-contract.json').write_text(json.dumps({
        'frozen': str(frozen), 'manifest_sha256': hashlib.sha256(manifest.encode()).hexdigest()}))
    (run / 'response-0.json').write_text(json.dumps({'text': json.dumps({
        'facts': [{'field_name': 'WBC', 'raw_value': '4.04', 'observation_id': 'f'}]})}))
    monkeypatch.setattr('sys.argv', ['score', str(tmp_path), '--page-index', '0', '--raw-candidates'])
    main()
    result = json.loads((tmp_path / 'raw-candidate-numeric-slice.json').read_text())
    assert result['raw_candidate_diagnostic_only'] is True
    assert result['clinical_acceptance'] is False
    assert result['results'][0]['counts']['numeric_match'] == 1
    assert not (run / 'record.json').exists()
