def test_download_artefact_version_returns_the_generated_docx(api_client):
    project = api_client.post("/projects", json={"name": "Download Test"}).json()
    run = api_client.post(
        f"/projects/{project['id']}/runs", json={"task_request": "Draft requirements"}
    ).json()
    versions = api_client.get(f"/runs/{run['id']}/artefact-versions").json()
    assert len(versions) == 1
    version = versions[0]

    resp = api_client.get(f"/artefact-versions/{version['id']}/download")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert resp.headers["content-disposition"] == 'attachment; filename="v0.1.docx"'
    assert resp.content[:2] == b"PK"  # docx files are zip archives


def test_download_missing_version_returns_404(api_client):
    resp = api_client.get("/artefact-versions/does-not-exist/download")
    assert resp.status_code == 404
