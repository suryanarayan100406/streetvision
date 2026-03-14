import json
import time
import urllib.request
import urllib.error

BASE = "http://localhost:8000"


def count_mission_detections(mission_id: int) -> tuple[int, set[int]]:
    status, potholes = request("GET", "/api/public/potholes?limit=500")
    if status != 200:
        return 0, set()
    prefix = f"drone/frames/{mission_id}/"
    matched = [p for p in (potholes or []) if str(p.get("image_path") or "").startswith(prefix)]
    ids = {int(p.get("id")) for p in matched if p.get("id") is not None}
    return len(matched), ids


def request(method, path, data=None, headers=None, timeout=30):
    url = BASE + path
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    if headers:
        for key, value in headers.items():
            req.add_header(key, value)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
        return response.status, (json.loads(raw) if raw else None)


def request_with_retry(method, path, data=None, headers=None, timeout=30, retries=4, delay=3):
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            return request(method, path, data=data, headers=headers, timeout=timeout)
        except (TimeoutError, urllib.error.URLError) as exc:
            last_error = exc
            print(f"retry_{attempt}_for={path}")
            time.sleep(delay)
    raise last_error


def main():
    status, _ = request("GET", "/health")
    print(f"health={status}")

    status, stats_before = request("GET", "/api/public/stats")
    before = int(stats_before.get("total_potholes", 0))
    print(f"before_total={before}")

    status, login = request(
        "POST",
        "/api/admin/auth/login",
        {"username": "admin", "password": "securepass123"},
    )
    token = login["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("auth=ok")

    candidates = [13, 12, 11, 10]
    any_positive = False

    for mission_id in candidates:
        status, mission_before = request("GET", f"/api/admin/drones/missions/{mission_id}", headers=headers)
        mission_name = mission_before.get("mission_name")
        print(f"\nmission={mission_id} ({mission_name})")
        print(f"mission_before_status={mission_before.get('processing_status')}")

        before_count, before_ids = count_mission_detections(mission_id)
        print(f"mission_before_detections={before_count}")

        status, reprocess = request_with_retry(
            "POST",
            f"/api/admin/drones/missions/{mission_id}/reprocess",
            headers=headers,
            timeout=120,
            retries=5,
            delay=4,
        )
        print(f"reprocess={reprocess.get('status')}")

        final_status = None
        for i in range(1, 25):
            time.sleep(5)
            status, mission = request_with_retry(
                "GET",
                f"/api/admin/drones/missions/{mission_id}",
                headers=headers,
                timeout=60,
                retries=3,
                delay=2,
            )
            final_status = mission.get("processing_status")
            print(f"poll_{mission_id}_{i}={final_status}")
            if final_status in {"COMPLETED", "FAILED"}:
                break

        after_count, after_ids = count_mission_detections(mission_id)
        new_ids = sorted(after_ids - before_ids)
        print(f"mission_after_detections={after_count}")
        print(f"mission_delta={after_count - before_count}")
        print(f"mission_new_ids={new_ids[:10]}")
        print(f"mission_final_status={final_status}")

        if final_status == "COMPLETED" and len(new_ids) > 0:
            any_positive = True
            print(f"\npositive_mission={mission_id}")
            break

    status, stats_after = request("GET", "/api/public/stats")
    after = int(stats_after.get("total_potholes", 0))

    print(f"\nafter_total={after}")
    print(f"delta={after - before}")
    print(f"positive_detection_created={any_positive}")


if __name__ == "__main__":
    main()
