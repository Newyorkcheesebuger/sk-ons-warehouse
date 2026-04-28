from datetime import datetime
from copy import deepcopy

from flask import Flask, jsonify, redirect, render_template, request, session, url_for


app = Flask(__name__)
app.secret_key = "preview-only-secret-key"

WAREHOUSES = ["보라매창고", "관악창고", "양천창고", "강남창고", "강동창고"]


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


SAMPLE_USERS = [
    [2, "김관리", "N1103813", "보라매", 1, "2026-04-20 09:30:00"],
    [3, "박대기", "N1103814", "강남", 0, "2026-04-26 15:12:00"],
]

SAMPLE_ELECTRIC = [
    [101, "전기차", "충전케이블", 12, "김관리", "2026-04-28 10:12:00", 2],
    [102, "전기차", "인버터", 3, "홍작업", "2026-04-28 09:01:00", 0],
]

SAMPLE_ACCESS = [
    [201, "기타", "작업장갑", 48, "김관리", "2026-04-28 08:41:00", 1],
    [202, "기타", "절연테이프", 15, "홍작업", "2026-04-27 17:35:00", 0],
]

INVENTORY_BY_ID = {row[0]: row for row in SAMPLE_ELECTRIC + SAMPLE_ACCESS}

SAMPLE_HISTORY = {
    101: [
        ["in", 5, "김관리", "2026-04-28 09:30:00"],
        ["out", -2, "홍작업", "2026-04-28 10:10:00"],
    ],
    201: [
        ["in", 20, "김관리", "2026-04-27 18:00:00"],
        ["out", -3, "박대기", "2026-04-28 08:40:00"],
    ],
}

SAMPLE_RECEIPTS = [
    {
        "id": 1,
        "date": "2026-04-28",
        "type": "in",
        "created_by": "김관리",
        "created_at": "2026-04-28 10:00:00",
        "items": [
            {
                "part_name": "작업장갑",
                "quantity": 10,
                "deliverer_dept": "보라매",
                "deliverer_name": "이기사",
                "receiver_dept": "강남",
                "receiver_name": "김관리",
                "purpose": "정기보급",
                "remark": "프리뷰 데이터",
            }
        ],
    }
]


def ensure_preview_session():
    if "user_id" not in session:
        as_admin = request.args.get("admin") == "1"
        session["user_id"] = 1
        session["user_name"] = "프리뷰사용자"
        session["employee_id"] = "N0000001"
        session["is_admin"] = as_admin


@app.before_request
def bootstrap_session():
    open_paths = {"/login", "/register", "/health"}
    if request.path.startswith("/static/") or request.path in open_paths:
        return
    ensure_preview_session()


@app.route("/")
def index():
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    return render_template("register.html")


@app.route("/login", methods=["POST"])
def login():
    session.clear()
    session["user_id"] = 1
    session["user_name"] = request.form.get("employee_id") or "프리뷰사용자"
    session["employee_id"] = request.form.get("employee_id") or "N0000001"
    session["is_admin"] = (request.form.get("employee_id") == "admin")
    if session["is_admin"]:
        return redirect(url_for("admin_dashboard"))
    return redirect(url_for("user_dashboard"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/dashboard")
def user_dashboard():
    if session.get("is_admin"):
        return redirect(url_for("admin_dashboard"))
    return render_template("user_dashboard.html", warehouses=WAREHOUSES)


@app.route("/admin/dashboard")
def admin_dashboard():
    session["is_admin"] = True
    return render_template(
        "admin_dashboard.html",
        users=deepcopy(SAMPLE_USERS),
        total_items=len(INVENTORY_BY_ID),
        total_quantity=sum(item[3] for item in INVENTORY_BY_ID.values()),
        warehouse_stats={"보라매창고": 2, "강남창고": 1, "양천창고": 1},
    )


@app.route("/admin/warehouse")
def admin_warehouse():
    session["is_admin"] = True
    return render_template("user_dashboard.html", warehouses=WAREHOUSES)


@app.route("/warehouse/<warehouse_name>")
def warehouse(warehouse_name):
    if warehouse_name not in WAREHOUSES:
        return render_template("preparing.html", warehouse_name=warehouse_name)
    return render_template("warehouse.html", warehouse_name=warehouse_name)


@app.route("/warehouse/<warehouse_name>/electric")
def electric_inventory(warehouse_name):
    return render_template(
        "electric_inventory.html",
        warehouse_name=warehouse_name,
        inventory=deepcopy(SAMPLE_ELECTRIC),
        is_admin=session.get("is_admin", False),
    )


@app.route("/warehouse/<warehouse_name>/access")
def access_inventory(warehouse_name):
    return render_template(
        "access_inventory.html",
        warehouse_name=warehouse_name,
        inventory=deepcopy(SAMPLE_ACCESS),
        is_admin=session.get("is_admin", False),
    )


@app.route("/search_inventory")
def search_inventory():
    query = (request.args.get("q") or "").strip()
    warehouse_name = (request.args.get("warehouse") or "").strip()

    rows = []
    for item in INVENTORY_BY_ID.values():
        inferred_warehouse = "보라매창고" if item[0] in (101, 201) else "강남창고"
        if query and query not in item[2]:
            continue
        if warehouse_name and warehouse_name != inferred_warehouse:
            continue
        rows.append([item[0], inferred_warehouse, item[1], item[2], item[3], item[4], item[5], item[6]])

    return render_template(
        "search_results.html",
        inventory=rows,
        query=query,
        warehouse=warehouse_name,
        is_admin=session.get("is_admin", False),
    )


@app.route("/photos/<int:item_id>")
def view_photos(item_id):
    item = INVENTORY_BY_ID.get(item_id)
    if not item:
        return render_template("photos.html", photos=[], item_id=item_id, item_info=None, is_admin=session.get("is_admin", False))
    item_info = (item[2], "보라매창고", item[1])
    photos = [
        [1, "sample1.jpg", "sample1.jpg", 245, "김관리", now_str(), "https://picsum.photos/seed/warehouse1/800/600"],
        [2, "sample2.jpg", "sample2.jpg", 198, "홍작업", now_str(), "https://picsum.photos/seed/warehouse2/800/600"],
    ]
    return render_template(
        "photos.html",
        photos=photos,
        item_id=item_id,
        item_info=item_info,
        is_admin=session.get("is_admin", False),
    )


@app.route("/inventory_history/<int:item_id>")
def inventory_history(item_id):
    item = INVENTORY_BY_ID.get(item_id)
    if item:
        item_info = (item[2], "보라매창고", item[1], item[3])
    else:
        item_info = None
    return render_template("inventory_history.html", item_info=item_info, history=SAMPLE_HISTORY.get(item_id, []))


@app.route("/receipt_history/<warehouse_name>")
def receipt_history(warehouse_name):
    return render_template(
        "receipt_history.html",
        warehouse_name=warehouse_name,
        receipts=deepcopy(SAMPLE_RECEIPTS),
        current_page=1,
        total_pages=1,
        total_count=len(SAMPLE_RECEIPTS),
        is_admin=session.get("is_admin", False),
    )


@app.route("/update_quantity", methods=["POST"])
def update_quantity():
    payload = request.get_json(silent=True) or {}
    item_id = int(payload.get("item_id", 0))
    change_type = payload.get("change_type", "in")
    quantity = int(payload.get("quantity", 0))
    item = INVENTORY_BY_ID.get(item_id)
    if not item:
        return jsonify({"success": False, "message": "프리뷰 항목이 없습니다."}), 404
    if change_type == "out":
        item[3] = max(0, item[3] - quantity)
    else:
        item[3] = item[3] + quantity
    item[4] = session.get("user_name", "프리뷰사용자")
    item[5] = now_str()
    return jsonify({"success": True, "new_quantity": item[3]})


@app.route("/add_inventory_item", methods=["POST"])
@app.route("/add_access_inventory_item", methods=["POST"])
def add_inventory_item():
    return redirect(request.referrer or url_for("user_dashboard"))


@app.route("/delete_inventory/<int:item_id>")
def delete_inventory(item_id):
    return redirect(request.referrer or url_for("user_dashboard"))


@app.route("/save_receipt_with_details", methods=["POST"])
def save_receipt_with_details():
    return jsonify({"success": True, "receipt_id": 9999, "message": "프리뷰 저장 성공"})


@app.route("/get_inventory_changes", methods=["POST"])
def get_inventory_changes():
    return jsonify({"success": True, "changes": [], "message": "프리뷰 모드"})


@app.route("/save_delivery_receipt", methods=["POST"])
@app.route("/send_delivery_receipt", methods=["POST"])
def delivery_receipt_actions():
    return jsonify({"success": True, "message": "프리뷰 처리 성공"})


@app.route("/delivery_receipt/<warehouse_name>")
def delivery_receipt(warehouse_name):
    return redirect(url_for("receipt_history", warehouse_name=warehouse_name))


@app.route("/approve_user/<int:user_id>")
@app.route("/delete_user/<int:user_id>")
@app.route("/delete_photo/<int:photo_id>")
@app.route("/delete_receipt/<int:receipt_id>")
@app.route("/debug_receipts/<warehouse_name>")
@app.route("/export_inventory")
def placeholder_redirect(**_kwargs):
    return redirect(request.referrer or url_for("user_dashboard"))


@app.route("/upload_photo/<int:item_id>", methods=["POST"])
def upload_photo(item_id):
    return jsonify({"success": True, "message": "프리뷰 업로드 성공", "url": f"https://picsum.photos/seed/{item_id}/800/600"})


@app.route("/health")
def health():
    return jsonify({"status": "healthy", "mode": "preview"})


if __name__ == "__main__":
    print("Preview mode: DB 없이 화면 확인 서버를 실행합니다.")
    print("주소: http://127.0.0.1:5000")
    print("관리자 화면: http://127.0.0.1:5000/admin/dashboard")
    app.run(debug=True, host="0.0.0.0", port=5000)
