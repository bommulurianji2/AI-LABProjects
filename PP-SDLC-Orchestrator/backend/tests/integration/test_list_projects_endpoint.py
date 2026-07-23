def test_list_projects_returns_created_projects_newest_first(api_client):
    assert api_client.get("/projects").json() == []

    first = api_client.post("/projects", json={"name": "First Project"}).json()
    second = api_client.post("/projects", json={"name": "Second Project"}).json()

    listed = api_client.get("/projects").json()
    assert [p["id"] for p in listed] == [second["id"], first["id"]]
