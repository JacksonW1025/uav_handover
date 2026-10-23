"""Search failures must not turn into claims that an original input is absent."""
import importlib.util
import io
from pathlib import Path
import tarfile
import zipfile

spec = importlib.util.spec_from_file_location('locate', Path(__file__).resolve().parents[1] / 'tools/p8_frozen_locate.py')
locate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(locate)


def test_archive_search_checks_nested_names_without_extracting(tmp_path):
    archive = tmp_path / 'backup.tar.gz'
    with tarfile.open(archive, 'w:gz') as t:
        t.addfile(tarfile.TarInfo('project/p8-refit/README.md'), io.BytesIO(b''))
    result = locate.archive_members(archive)
    assert result['status'] == 'member_names_searched'
    assert result['matches'] == ['project/p8-refit/README.md']
    assert not (tmp_path / 'project').exists()
    data = archive.read_bytes()
    assert locate.archive_members('historical.tar.gz', data) == result


def test_corrupt_or_unsupported_archive_is_not_negative_evidence(tmp_path):
    archive = tmp_path / 'broken.tar.gz'
    archive.write_bytes(b'not an archive')
    assert locate.archive_members(archive)['status'] == 'read_error'
    assert locate.archive_members('unknown.7z')['status'] == 'unsupported_7z_not_searched'


def test_zip_names_include_original_input_and_do_not_extract(tmp_path):
    archive = tmp_path / 'backup.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr('project/notes/target-interface/experiments/common.py', '')
    result = locate.archive_members(archive)
    assert result['status'] == 'member_names_searched'
    assert len(result['matches']) == 1
    assert not (tmp_path / 'project').exists()
