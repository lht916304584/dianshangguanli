import requests, json

r = requests.post('http://localhost:8000/api/v1/user/login', json={"phone": "13800000001", "password": "test123"})
token = r.json().get("token", "")
print("Token OK" if token else "Login failed")

r2 = requests.post(
    "http://localhost:8000/api/v1/detail/plan",
    json={"product_info": "纯棉短袖T恤女夏季新款宽松百搭显瘦打底衫", "platform": "pinduoduo", "category": "女装"},
    headers={"Authorization": "Bearer " + token},
    timeout=90,
)
d = r2.json()
print("Success:", d.get("success"))
sp = d.get("selling_points", {})
print("Core points:", len(sp.get("core_points", [])))
print("Support points:", len(sp.get("support_points", [])))
for p in sp.get("core_points", []):
    print(f"  - {p.get('title')}: {p.get('detail')}")
ps = d.get("page_structure", [])
print("Pages:", len(ps))
for s in ps:
    print(f"  S{s.get('screen')}: {s.get('title')}")
print("Img prompts:", len(d.get("image_prompts", [])))
print("Images:", len(d.get("images", [])))
