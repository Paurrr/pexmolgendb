"""etag 가 남의 변경을 잡고 내 무변경 저장에는 반응하지 않는지.

배너의 값어치는 전부 여기에 달려 있다. 놓치면 알림이 안 뜨고, 과하게 잡으면
"바뀌었습니다" 가 계속 떠서 아무도 안 본다.
"""

from genviewer.service.repo.device import DeviceRepository, etag_key
from genviewer.service.repo.parameter import ParameterRepository
from genviewer.service.repo.process import ProcessRepository

# db 픽스처가 GENDB_TEST_PG_DSN 없이 돌면 알아서 skip 한다.
COLUMNS = ["reserved_key", "cds_inst_term_name"]


def _seed(db, name="sf2p", devices=("nfet_b",)):
    pr, dr = ProcessRepository(db), DeviceRepository(db)
    pid = pr.get_or_create_id(name)
    made = [
        dr.upsert_device(
            pid, {"name": d, "celltype": "NFET", "description": "", "order": i}
        )
        for i, d in enumerate(devices)
    ]
    return pid, dr, made


def test_unchanged_process_keeps_the_same_etag(db):
    pid, dr, _ = _seed(db)
    assert etag_key(dr.etag(pid)) == etag_key(dr.etag(pid))


def test_another_users_insert_changes_it(db):
    pid, dr, _ = _seed(db)
    before = dr.etag(pid)
    dr.upsert_device(
        pid,
        {"name": "pfet_b", "celltype": "PFET", "description": "", "order": 1},
        actor="bob",
    )
    after = dr.etag(pid)
    assert etag_key(after) != etag_key(before)
    assert after["who"] == "bob"


def test_another_users_edit_changes_it(db):
    pid, dr, made = _seed(db)
    before = dr.etag(pid)
    dr.upsert_devices(
        pid,
        [{**made[0], "description": "bob 이 고침"}],
        actor="bob",
    )
    after = dr.etag(pid)
    assert etag_key(after) != etag_key(before)
    assert after["who"] == "bob"


def test_another_users_delete_changes_it(db):
    pid, dr, made = _seed(db, devices=("nfet_b", "pfet_b"))
    before = dr.etag(pid)
    dr.upsert_devices(
        pid,
        [made[0]],
        deleted={made[1]["id"]: made[1]["version"]},
        actor="bob",
    )
    assert etag_key(dr.etag(pid)) != etag_key(before)


def test_a_no_op_save_does_not_change_it(db):
    """저장할 때마다 배너가 뜨면 아무도 배너를 안 본다.

    save_all 은 손대지 않은 device 까지 전부 보내므로, upsert_devices 의
    IS DISTINCT FROM 가드가 없으면 여기서 version 이 올라간다.
    """
    pid, dr, made = _seed(db, devices=("nfet_b", "pfet_b"))
    before = dr.etag(pid)
    dr.upsert_devices(pid, made, actor="me")
    assert etag_key(dr.etag(pid)) == etag_key(before)


def test_a_tab_save_changes_it(db):
    """자식 테이블만 바꿔도 잡혀야 한다. device.version 이 집계 버전이다."""
    pid, dr, made = _seed(db)
    before = dr.etag(pid)
    ParameterRepository(db).replace_many_for_device(
        made[0]["id"],
        {"inst_terms": (COLUMNS, [{"reserved_key": "DRN", "cds_inst_term_name": "d"}])},
        expected_version=made[0]["version"],
        actor="bob",
    )
    assert etag_key(dr.etag(pid)) != etag_key(before)


def test_a_sibling_process_is_invisible(db):
    """etag 는 process 단위다. 옆 process 가 바뀌었다고 배너가 뜨면 안 된다."""
    pid, dr, _ = _seed(db, "sf2p")
    before = dr.etag(pid)
    _seed(db, "sf4u", devices=("nfet_x",))
    assert etag_key(dr.etag(pid)) == etag_key(before)


def test_etag_key_ignores_who(db):
    pid, dr, _ = _seed(db)
    etag = dr.etag(pid)
    assert etag_key({**etag, "who": "누구든"}) == etag_key(etag)
    assert etag_key(None) is None
