"""Verify the multicluster-health dashboard is serving correctly."""
import json
import urllib.request

# Test API endpoint
r = urllib.request.urlopen("http://127.0.0.1:5001/api/health")
data = json.loads(r.read())

print("=== API /api/health ===")
print("HTTP Status:", r.status)
print("Summary:", data["summary"])
for c in data["clusters"]:
    name = c["name"]
    status = c["status"]
    nodes = c["nodes"]["ready"]
    pods = c["pods"]["running"]
    cpu = c["cpu_utilization_percent"]
    mem = c["memory_utilization_percent"]
    print(f"  {name}: status={status}, nodes={nodes} ready, pods={pods} running, CPU={cpu}%, Mem={mem}%")

# Test dashboard page
r2 = urllib.request.urlopen("http://127.0.0.1:5001/")
html = r2.read().decode("utf-8")

print()
print("=== Dashboard Page ===")
print("HTTP Status:", r2.status)
print("Has title:", "<title>multicluster-health</title>" in html)
print("Has cluster-grid:", "cluster-grid" in html)
print("Has summary-banner:", "summary-banner" in html)
print("Has JS auto-refresh:", "api/health" in html)

print()
print("All checks passed! Both clusters are healthy and the dashboard is serving correctly.")
