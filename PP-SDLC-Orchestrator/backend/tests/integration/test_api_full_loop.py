"""HTTP-level end-to-end test: create project -> start run -> fetch artefact
version -> submit review -> assert phase unlock. Uses the `api_client`
fixture (see tests/conftest.py) for an isolated temp database per test.
"""


def test_full_orchestrated_loop_over_http(api_client):
    agents = api_client.get("/agents").json()
    assert any(a["id"] == "analysis" for a in agents)

    create_resp = api_client.post("/projects", json={"name": "Employee Leave Request"})
    assert create_resp.status_code == 201
    project = create_resp.json()
    assert project["current_phase"] == "analysis"
    assert project["phase_status"] == "pending"

    run_resp = api_client.post(
        f"/projects/{project['id']}/runs", json={"task_request": "Build an employee leave request workflow"}
    )
    assert run_resp.status_code == 201
    run = run_resp.json()
    assert run["state"] == "waiting_for_human_review"

    versions_resp = api_client.get(f"/runs/{run['id']}/artefact-versions")
    assert versions_resp.status_code == 200
    versions = versions_resp.json()
    assert len(versions) == 1
    assert versions[0]["version_label"] == "v0.1"
    assert versions[0]["status"] == "draft"

    # simulate a reviewer user existing (session-1 has no auth yet - pass a raw id)
    review_resp = api_client.post(
        f"/runs/{run['id']}/review",
        json={"reviewer_id": "test-reviewer", "decision": "approved", "comments": ["Looks good"]},
    )
    assert review_resp.status_code == 200
    updated_project = review_resp.json()
    assert updated_project["current_phase"] == "ux_design"
    assert updated_project["phase_status"] == "pending"

    run_status = api_client.get(f"/runs/{run['id']}").json()
    assert run_status["state"] == "completed"
