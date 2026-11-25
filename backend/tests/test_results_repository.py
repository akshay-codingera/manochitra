import json
from pathlib import Path

import pytest

from app.persistence.results_repository import ModelRunsRepository, ResultsRepository


@pytest.fixture(autouse=True)
def ensure_tmp_path_ready(tmp_path: Path) -> Path:
    """Ensure the isolated temporary directory and its parents exist on all platforms."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    return tmp_path


def test_repository_initialises_empty_results_file(tmp_path):
    path = tmp_path / 'results.json'
    repository = ResultsRepository(path)
    assert path.exists()
    assert repository.all() == []
    payload = json.loads(path.read_text(encoding='utf-8'))
    assert payload['schema_version'] == 1


def test_upsert_adds_then_replaces_by_concept_id(tmp_path):
    repository = ResultsRepository(tmp_path / 'results.json')
    repository.upsert({'concept_id': 'circle', 'status': 'FAIL'})
    repository.upsert({'concept_id': 'circle', 'status': 'PASS', 'svg': '<svg />'})
    repository.upsert({'concept_id': 'photosynthesis', 'status': 'PASS'})
    results = repository.all()
    assert len(results) == 2
    assert repository.by_concept('circle')['status'] == 'PASS'
    assert repository.by_concept('missing') is None


def test_replace_all_replaces_previous_snapshot(tmp_path):
    repository = ResultsRepository(tmp_path / 'results.json')
    repository.upsert({'concept_id': 'circle', 'status': 'FAIL'})
    repository.replace_all([{'concept_id': 'states-of-matter', 'status': 'PASS'}])
    assert repository.all() == [{'concept_id': 'states-of-matter', 'status': 'PASS'}]


def test_corrupt_json_fails_clearly(tmp_path):
    path = tmp_path / 'results.json'
    path.write_text('{broken', encoding='utf-8')
    repository = ResultsRepository(path)
    with pytest.raises(RuntimeError, match='Could not read results file'):
        repository.all()


def test_model_runs_repository_initialises_empty_runs_file(tmp_path):
    path = tmp_path / 'model_runs.json'
    repo = ModelRunsRepository(path)
    assert path.exists()
    assert repo.all() == []
    payload = json.loads(path.read_text(encoding='utf-8'))
    assert payload['schema_version'] == 1
    assert payload['runs'] == []


def test_model_runs_repository_does_not_overwrite_between_different_models(tmp_path):
    path = tmp_path / 'model_runs.json'
    repo = ModelRunsRepository(path)

    # 1. Add run for concept 'circle' using gemini-3.5-flash-lite
    run_lite = {
        'concept_id': 'circle',
        'model': 'gemini-3.5-flash-lite',
        'status': 'PASS',
        'svg': '<svg id="lite"/>',
    }
    repo.upsert(run_lite)

    # 2. Add run for concept 'circle' using gemini-3.8-flash
    run_flash = {
        'concept_id': 'circle',
        'model': 'gemini-3.8-flash',
        'status': 'FAIL',
        'svg': '<svg id="flash"/>',
    }
    repo.upsert(run_flash)

    # Both runs MUST coexist: neither model overwrites the other!
    runs = repo.all()
    assert len(runs) == 2

    stored_lite = repo.by_concept_and_model('circle', 'gemini-3.5-flash-lite')
    assert stored_lite is not None
    assert stored_lite['status'] == 'PASS'
    assert stored_lite['svg'] == '<svg id="lite"/>'

    stored_flash = repo.by_concept_and_model('circle', 'gemini-3.8-flash')
    assert stored_flash is not None
    assert stored_flash['status'] == 'FAIL'
    assert stored_flash['svg'] == '<svg id="flash"/>'


def test_model_runs_repository_updates_same_model_run_in_place(tmp_path):
    path = tmp_path / 'model_runs.json'
    repo = ModelRunsRepository(path)

    repo.upsert({'concept_id': 'circle', 'model': 'gemini-3.5-flash-lite', 'status': 'PASS'})
    repo.upsert({'concept_id': 'circle', 'model': 'gemini-3.8-flash', 'status': 'FAIL'})

    # Re-run gemini-3.8-flash with a repair that passes:
    repo.upsert({'concept_id': 'circle', 'model': 'gemini-3.8-flash', 'status': 'PASS', 'repaired': True})

    runs = repo.all()
    assert len(runs) == 2  # Still 2 runs, not 3
    assert repo.by_concept_and_model('circle', 'gemini-3.5-flash-lite')['status'] == 'PASS'
    assert repo.by_concept_and_model('circle', 'gemini-3.8-flash')['status'] == 'PASS'
    assert repo.by_concept_and_model('circle', 'gemini-3.8-flash').get('repaired') is True


def test_results_json_remains_separate_from_model_runs(tmp_path):
    results_path = tmp_path / 'results.json'
    runs_path = tmp_path / 'model_runs.json'

    results_repo = ResultsRepository(results_path)
    runs_repo = ModelRunsRepository(runs_path)

    results_repo.upsert({'concept_id': 'pythagoras', 'status': 'PASS', 'model': 'gemini-3.5-flash-lite'})
    runs_repo.upsert({'concept_id': 'pythagoras', 'status': 'PASS', 'model': 'gemini-3.8-flash'})

    # results.json contains only the canonical entry
    assert len(results_repo.all()) == 1
    assert results_repo.all()[0]['model'] == 'gemini-3.5-flash-lite'

    # model_runs.json contains the experimental entry
    assert len(runs_repo.all()) == 1
    assert runs_repo.all()[0]['model'] == 'gemini-3.8-flash'

