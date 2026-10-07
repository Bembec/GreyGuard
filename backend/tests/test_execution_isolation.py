from types import SimpleNamespace
import pytest
from backend.app import execution_isolation as isolation
@pytest.fixture()
def isolated(tmp_path,monkeypatch):monkeypatch.setattr(isolation,"database_path",tmp_path/"isolation.db");isolation.initialize_execution_isolation();return isolation
def enable(module):return module.update_config(True,"greyguard-sandbox:test",.5,256,64,30,"owner")
def test_isolation_is_disabled_by_default(isolated):
 assert isolated.get_config()["enabled"] is False
 with pytest.raises(PermissionError,match="disabled"):isolated.docker_command("SANDBOX_PROBE","iso_test")
def test_docker_command_enforces_all_boundaries(isolated):
 enable(isolated);command=isolated.docker_command("SANDBOX_PROBE","iso_test");joined=" ".join(command)
 for control in ("--network none","--read-only","--user 65532:65532","--cap-drop ALL","no-new-privileges:true","--pids-limit 64","--cpus 0.5","--memory 256m"):assert control in joined
 assert command[0]=="docker" and "sh" not in command and "bash" not in command
def test_arbitrary_job_is_rejected(isolated):
 enable(isolated)
 with pytest.raises(PermissionError,match="predefined"):isolated.docker_command("RUN_COMMAND","iso_test")
def test_predefined_job_records_evidence(isolated):
 enable(isolated);result=isolated.run_predefined_job("SANDBOX_PROBE","owner",runner=lambda *a,**k:SimpleNamespace(returncode=0,stdout="ready",stderr=""));assert result["status"]=="SUCCEEDED";assert isolated.execution_history()[0]["result"]=="ready"
def test_resource_limits_reject_unsafe_values(isolated):
 with pytest.raises(ValueError,match="outside"):isolated.update_config(True,"greyguard-sandbox:test",8,4096,1000,600,"owner")
def _insert_running(module,execution_id):
 with module.sqlite3.connect(module.database_path) as c:c.execute("INSERT INTO isolation_executions VALUES(?,?,?,?,?,?,?,?,?)",(execution_id,"SANDBOX_PROBE","2026-10-07T00:00:00+00:00","owner","RUNNING","greyguard-"+execution_id,None,None,None))
def test_emergency_terminate_kills_jobs_started_by_another_worker(isolated):
 # The job exists only in the database, as if another worker process started it.
 execution_id="iso_"+"a"*32;_insert_running(isolated,execution_id);killed=[]
 result=isolated.emergency_terminate("owner",runner=lambda command,**k:killed.append(command))
 assert result["terminated"]==[execution_id] and killed==[["docker","kill","greyguard-"+execution_id]]
 assert isolated.execution_history()[0]["status"]=="TERMINATED"
def test_emergency_terminate_refuses_unexpected_container_names(isolated):
 with isolated.sqlite3.connect(isolated.database_path) as c:c.execute("INSERT INTO isolation_executions VALUES(?,?,?,?,?,?,?,?,?)",("iso_bad","SANDBOX_PROBE","2026-10-07T00:00:00+00:00","owner","RUNNING","postgres",None,None,None))
 killed=[];result=isolated.emergency_terminate("owner",runner=lambda command,**k:killed.append(command))
 assert result["count"]==0 and killed==[]
def test_terminated_status_is_not_overwritten_when_the_job_returns(isolated):
 enable(isolated)
 def runner(command,**k):
  isolated.emergency_terminate("owner",runner=lambda *a,**kk:None)
  return SimpleNamespace(returncode=137,stdout="",stderr="killed")
 result=isolated.run_predefined_job("SANDBOX_PROBE","owner",runner=runner)
 assert result["status"]=="TERMINATED" and isolated.execution_history()[0]["status"]=="TERMINATED"
