from pathlib import Path
import pytest
from backend.app import isolation_operations as operations
@pytest.fixture()
def isolated(tmp_path,monkeypatch):
 monkeypatch.setattr(operations,"database_path",tmp_path/"ops.db");monkeypatch.setattr(operations,"workspace_root",(tmp_path/"workspaces").resolve());monkeypatch.setattr(operations,"quarantine_root",(tmp_path/"quarantine").resolve());operations.initialize_isolation_operations();return operations
def test_workspace_is_per_agent_and_destroyed(isolated):
 item=isolated.create_workspace("agent-one");path=Path(item["path"]);assert path.exists();result=isolated.destroy_workspace(item["workspace_id"],"owner");assert result["status"]=="DESTROYED" and not path.exists()
def test_workspace_rejects_path_escape(isolated):
 with pytest.raises(ValueError,match="unsafe"):isolated.create_workspace("../escape")
def test_kill_switch_blocks_workspace_and_kubernetes_jobs(isolated):
 isolated.update_operations(True,False,[],[],"owner")
 with pytest.raises(PermissionError,match="kill switch"):isolated.create_workspace("agent")
 with pytest.raises(PermissionError,match="kill switch"):isolated.kubernetes_job_manifest("agent","job")
def test_network_requires_both_allowlists(isolated):
 with pytest.raises(ValueError,match="requires"):isolated.update_operations(False,True,["api.example.com:443"],[],"owner")
def test_artifact_quarantine_moves_and_scans(isolated):
 workspace=isolated.create_workspace("agent");source=Path(workspace["path"])/"result.txt";source.write_text("safe evidence",encoding="utf-8");artifact=isolated.quarantine_artifact(workspace["workspace_id"],source);assert not source.exists();result=isolated.scan_artifact(artifact["artifact_id"],lambda path:{"clean":True,"engine":"test","detail":"clean"});assert result["status"]=="CLEAN" and result["released"] is False
def test_quarantine_rejects_host_file(isolated,tmp_path):
 workspace=isolated.create_workspace("agent");outside=tmp_path/"outside.txt";outside.write_text("host")
 with pytest.raises(PermissionError,match="inside"):isolated.quarantine_artifact(workspace["workspace_id"],outside)
def test_kubernetes_manifest_is_restricted(isolated):
 manifest=isolated.kubernetes_job_manifest("agent","job-1");spec=manifest["spec"]["template"]["spec"];container=spec["containers"][0];assert manifest["metadata"]["namespace"]=="greyguard-sandbox";assert spec["automountServiceAccountToken"] is False;assert container["securityContext"]["capabilities"]["drop"]==["ALL"]
def test_scan_reports_malicious_artifacts(isolated):
 workspace=isolated.create_workspace("agent");source=Path(workspace["path"])/"result.txt";source.write_text("evidence",encoding="utf-8");artifact=isolated.quarantine_artifact(workspace["workspace_id"],source)
 result=isolated.scan_artifact(artifact["artifact_id"],lambda path:{"clean":False,"engine":"test","detail":"Eicar-Test-Signature FOUND"})
 assert result["status"]=="MALICIOUS"
 assert isolated.get_operations()["artifacts"][0]["scan_result"]=="Eicar-Test-Signature FOUND"
def test_scan_failure_never_reports_clean(isolated):
 workspace=isolated.create_workspace("agent");source=Path(workspace["path"])/"result.txt";source.write_text("evidence",encoding="utf-8");artifact=isolated.quarantine_artifact(workspace["workspace_id"],source)
 def _broken_scanner(path):raise RuntimeError("scanner unreachable")
 result=isolated.scan_artifact(artifact["artifact_id"],_broken_scanner)
 assert result["status"]=="SCAN_FAILED"
 record=isolated.get_operations()["artifacts"][0]
 assert record["status"]=="SCAN_FAILED" and "unreachable" in record["scan_result"]
def test_scan_unknown_artifact_raises(isolated):
 with pytest.raises(KeyError):isolated.scan_artifact("art_does_not_exist",lambda path:{"clean":True})
def test_write_and_quarantine_creates_artifact_without_opening_content(isolated):
 workspace=isolated.create_workspace("agent")
 result=isolated.write_and_quarantine_artifact(workspace["workspace_id"],"payload.bin",b"\x00\x01binary-looking-content")
 assert result["status"]=="QUARANTINED"
 assert result["size_bytes"]==len(b"\x00\x01binary-looking-content")
 assert not (Path(workspace["path"])/"payload.bin").exists()
def test_write_and_quarantine_rejects_unsafe_filename(isolated):
 workspace=isolated.create_workspace("agent")
 with pytest.raises(ValueError,match="unsafe"):isolated.write_and_quarantine_artifact(workspace["workspace_id"],"../escape.bin",b"data")
def test_write_and_quarantine_rejects_oversized_content(isolated,monkeypatch):
 monkeypatch.setattr(operations,"MAX_UPLOAD_BYTES",10)
 workspace=isolated.create_workspace("agent")
 with pytest.raises(ValueError,match="exceeds"):isolated.write_and_quarantine_artifact(workspace["workspace_id"],"payload.bin",b"this content is definitely too long")
def test_write_and_quarantine_requires_active_workspace(isolated):
 with pytest.raises(KeyError):isolated.write_and_quarantine_artifact("ws_does_not_exist","payload.bin",b"data")
