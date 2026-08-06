from datetime import datetime
import hashlib
import io
import os
import streamlit as st
from pymongo import MongoClient
import cloudinary
import cloudinary.uploader
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# 1. เชื่อมต่อกับ MongoDB
mongo_uri = st.secrets["MONGO_URI"]
client = MongoClient(mongo_uri)
db = client["worklog_db"]
collection = db["logs"]
profile_collection = db["profiles"]
user_auth_collection = db["users"]
visitor_collection = db["visitors"]

# สร้าง Index เพื่อให้การค้นหาและเรียงลำดับข้อมูลใน MongoDB ทำงานได้รวดเร็วขึ้น
collection.create_index([("author", 1), ("created_at", -1)])
profile_collection.create_index([("author", 1)], unique=True)
user_auth_collection.create_index([("username", 1)], unique=True)
visitor_collection.create_index([("profile_owner", 1), ("visited_at", -1)])

# ตั้งค่า Cloudinary สำหรับเก็บไฟล์บน Cloud
cloudinary.config(
    cloud_name=st.secrets["cloudinary"]["cloud_name"],
    api_key=st.secrets["cloudinary"]["api_key"],
    api_secret=st.secrets["cloudinary"]["api_secret"],
    secure=True
)

# ฟังก์ชันช่วยปรับแต่ง URL ของ Cloudinary ให้โหลดไวขึ้น (Auto Quality & Resizing)
def optimize_cloudinary_url(url, width=None):
  if "cloudinary.com" in url and "/upload/" in url:
    parts = url.split("/upload/")
    transformations = "f_auto,q_auto"
    if width:
      transformations += f",w_{width}"
    return f"{parts[0]}/upload/{transformations}/{parts[1]}"
  return url

# ฟังก์ชันสำหรับสร้างรายงาน PDF ด้วย ReportLab
def generate_pdf_report(username, logs_data):
  buffer = io.BytesIO()
  p = canvas.Canvas(buffer, pagesize=letter)
  width, height = letter
  
  p.setFont("Helvetica-Bold", 16)
  p.drawString(50, height - 50, f"Work Log Report - {username}")
  
  p.setFont("Helvetica", 10)
  p.drawString(50, height - 70, f"Generated Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
  p.line(50, height - 80, width - 50, height - 80)
  
  y_position = height - 110
  p.setFont("Helvetica", 10)
  
  for idx, log in enumerate(logs_data, 1):
    if y_position < 100:
      p.showPage()
      p.setFont("Helvetica", 10)
      y_position = height - 50
      
    p.setFont("Helvetica-Bold", 11)
    p.drawString(50, y_position, f"{idx}. [{log.get('category')}] {log.get('title')} ({log.get('date')})")
    y_position -= 18
    
    p.setFont("Helvetica", 10)
    content_text = log.get('content', '')
    p.drawString(70, y_position, f"Details: {content_text[:80]}...")
    y_position -= 30
    
  p.save()
  buffer.seek(0)
  return buffer.getvalue()

# ตั้งค่าหน้าเว็บแบบ Wide Mode
st.set_page_config(page_title="My Daily Work Log", page_icon="💻", layout="wide")

# เพิ่ม Custom CSS
st.markdown("""
    <style>
    .main-title {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0px;
    }
    .sub-title {
        font-size: 1.1rem;
        color: #4B5563;
        margin-bottom: 20px;
    }
    .card-box {
        background-color: #F8FAFC;
        padding: 30px;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    </style>
""", unsafe_allow_html=True)

def hash_password(password):
  return hashlib.sha256(password.encode()).hexdigest()

# จัดการ Session State ของระบบล็อกอิน และตัวรีเซ็ตช่องอัปโหลดไฟล์
if "logged_in_user" not in st.session_state:
  st.session_state.logged_in_user = None
if "uploader_key" not in st.session_state:
  st.session_state.uploader_key = 0

# =====================================================================
# ส่วนที่ 1: หน้าล็อกอิน / สมัครสมาชิก
# =====================================================================
if not st.session_state.logged_in_user:
  st.markdown("<div class='main-title' style='text-align: center;'>💻 My Daily Work Log & Social Space</div>", unsafe_allow_html=True)
  st.markdown("<div class='sub-title' style='text-align: center;'>ระบบบันทึกรายงานการทำงานประจำวัน และพื้นที่แชร์ผลงานร่วมกันอย่างปลอดภัย</div>", unsafe_allow_html=True)
  st.markdown("<br>", unsafe_allow_html=True)

  col1, col2, col3 = st.columns([1, 1.2, 1])
  
  with col2:
    st.markdown("<div class='card-box'>", unsafe_allow_html=True)
    auth_tab1, auth_tab2 = st.tabs(["🔑 เข้าสู่ระบบ", "📝 สมัครสมาชิก"])

    with auth_tab1:
      st.subheader("ยินดีต้อนรับกลับมา!")
      login_user = st.text_input("👤 ชื่อผู้ใช้งาน", key="l_user").strip()
      login_pass = st.text_input("🔑 รหัสผ่าน", type="password", key="l_pass")
      st.markdown("<br>", unsafe_allow_html=True)
      
      if st.button("🚀 เข้าสู่ระบบทันที", use_container_width=True):
        if login_user and login_pass:
          user_record = user_auth_collection.find_one({"username": login_user})
          if user_record and user_record["password"] == hash_password(login_pass):
            st.session_state.logged_in_user = login_user
            st.success("เข้าสู่ระบบสำเร็จ!")
            st.rerun()
          else:
            st.error("❌ ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
        else:
          st.warning("⚠️ กรุณากรอกข้อมูลให้ครบถ้วน")

    with auth_tab2:
      st.subheader("สร้างบัญชีใหม่")
      reg_user = st.text_input("👤 กำหนดชื่อผู้ใช้งาน", key="r_user").strip()
      reg_pass = st.text_input("🔑 กำหนดรหัสผ่าน", type="password", key="r_pass")
      st.markdown("<br>", unsafe_allow_html=True)

      if st.button("✨ ยืนยันการสมัครสมาชิก", use_container_width=True):
        if reg_user and reg_pass:
          existing_user = user_auth_collection.find_one({"username": reg_user})
          if existing_user:
            st.error("❌ ชื่อผู้ใช้นี้ถูกใช้งานแล้ว กรุณาใช้ชื่ออื่น")
          else:
            user_auth_collection.insert_one({
                "username": reg_user,
                "password": hash_password(reg_pass),
                "created_at": datetime.now()
            })
            profile_collection.insert_one({
                "author": reg_user,
                "bio": "ยังไม่ได้เขียนอธิบายตัวเอง...",
                "avatar": ""
            })
            st.success("🎉 สมัครสมาชิกสำเร็จ! กรุณากลับไปที่แท็บ 'เข้าสู่ระบบ'")
        else:
          st.warning("⚠️ กรุณากรอกชื่อและรหัสผ่านให้ครบถ้วน")
          
    st.markdown("</div>", unsafe_allow_html=True)

  st.stop() 

# =====================================================================
# ส่วนที่ 2: หน้าหลักหลัง Login
# =====================================================================
clean_user = st.session_state.logged_in_user

st.sidebar.markdown(f"### 👋 สวัสดีคุณ, **{clean_user}**")
st.sidebar.markdown("---")

nav_mode = st.sidebar.radio(
    "📌 เมนูหลัก", 
    ["📁 งานของฉัน & จัดการพอร์ต", "🌐 หน้าเยี่ยมชมโปรไฟล์เพื่อนๆ"]
)

st.sidebar.markdown("---")
st.sidebar.subheader("🎨 ตั้งค่าโปรไฟล์ส่วนตัว")
user_profile = profile_collection.find_one({"author": clean_user}) or {"author": clean_user, "bio": "...", "avatar": ""}

with st.sidebar.form("profile_form"):
  new_bio = st.text_area("คำอธิบายสั้นๆ (Bio):", value=user_profile.get("bio", ""))
  avatar_file = st.file_uploader("เปลี่ยนรูปโปรไฟล์", type=["png", "jpg", "jpeg"])
  save_profile = st.form_submit_button("💾 บันทึกโปรไฟล์", use_container_width=True)

  if save_profile:
    avatar_filename = user_profile.get("avatar", "")
    if avatar_file is not None:
      upload_avatar = cloudinary.uploader.upload(avatar_file, resource_type="image", folder="worklog_avatars")
      avatar_filename = upload_avatar.get("secure_url")
    
    profile_collection.update_one(
        {"author": clean_user},
        {"$set": {"bio": new_bio, "avatar": avatar_filename}},
        upsert=True
    )
    st.success("บันทึกโปรไฟล์สำเร็จ!")
    st.rerun()

st.sidebar.markdown("---")
if st.sidebar.button("🚪 ออกจากระบบ", use_container_width=True, type="secondary"):
  st.session_state.logged_in_user = None
  st.rerun()


# ==========================================
# โหมดที่ 1: งานของฉัน & จัดการ (My Work Log)
# ==========================================
if nav_mode == "📁 งานของฉัน & จัดการพอร์ต":
  st.markdown(f"<div class='main-title'>📁 พอร์ตโฟลิโอและบันทึกงานของคุณ</div>", unsafe_allow_html=True)
  st.markdown("<br>", unsafe_allow_html=True)
  
  col_p1, col_p2 = st.columns([1, 6])
  with col_p1:
    avatar_img = user_profile.get("avatar", "")
    if avatar_img:
      optimized_avatar = optimize_cloudinary_url(avatar_img, width=200)
      st.image(optimized_avatar, width=120)
    else:
      st.info("🖼️ ไม่มีรูปโปรไฟล์")
  with col_p2:
    st.subheader(f"ผู้ใช้งาน: {clean_user}")
    st.write(f"**Bio:** {user_profile.get('bio', 'ยังไม่มีคำอธิบาย')}")

  # กล่องจดหมายผู้เข้าชมโปรไฟล์
  st.markdown("---")
  st.subheader("📬 กล่องจดหมายผู้เข้าชมโปรไฟล์ (Profile Viewers)")
  
  recent_visitors = list(visitor_collection.find({"profile_owner": clean_user}).sort("visited_at", -1).limit(10))
  
  if recent_visitors:
    st.info("👀 มีผู้ใช้งานแวะมาเยี่ยมชมโปรไฟล์ของคุณ:")
    for v_item in recent_visitors:
      v_name = v_item.get("visitor", "ผู้ใช้ไม่ระบุตัวตน")
      v_time = v_item.get("visited_at").strftime("%Y-%m-%d %H:%M") if v_item.get("visited_at") else "-"
      st.markdown(f"- 👤 **{v_name}** เข้ามาเยี่ยมชมโปรไฟล์ของคุณเมื่อวันที่ {v_time}")
  else:
    st.caption("📭 ยังไม่มีใครมาเยี่ยมชมโปรไฟล์ของคุณในขณะนี้ ลองแวะไปส่องเพื่อนก่อน เผื่อเพื่อนจะแวะมาส่องกลับ!")

  st.divider()

  with st.form("worklog_form"):
    st.subheader("📝 เพิ่มบันทึกงานใหม่")
    
    f_col1, f_col2 = st.columns(2)
    with f_col1:
      log_date = st.date_input("วันที่ปฏิบัติงาน", datetime.today())
    with f_col2:
      category = st.selectbox(
          "หมวดหมู่งาน", ["Coding", "Meeting", "Debugging", "Learning", "Other"]
      )
      
    title = st.text_input("หัวข้อเรื่อง / งานที่ทำ")
    content = st.text_area("รายละเอียดการทำงาน")

    uploaded_files = st.file_uploader(
        "แนบไฟล์หลักฐาน (เลือกได้หลายไฟล์: รูปภาพ / เอกสาร / วิดีโอ)", 
        type=["png", "jpg", "jpeg", "pdf", "mp4", "mov", "avi"],
        accept_multiple_files=True,
        key=f"uploader_{st.session_state.uploader_key}"
    )

    submitted = st.form_submit_button("💾 บันทึกข้อมูลงานนี้", use_container_width=True)

    if submitted:
      if title and content:
        if "form_submitted" not in st.session_state:
          st.session_state.form_submitted = False

        if not st.session_state.form_submitted:
          st.session_state.form_submitted = True

          saved_file_urls = []
          if uploaded_files:
            for uploaded_file in uploaded_files:
              upload_result = cloudinary.uploader.upload(
                  uploaded_file,
                  resource_type="auto",
                  folder="worklog_uploads"
              )
              saved_file_urls.append(upload_result.get("secure_url"))

          log_data = {
              "author": clean_user,
              "date": str(log_date),
              "title": title,
              "category": category,
              "content": content,
              "attachments": saved_file_urls,
              "comments": [],
              "likes": [],
              "created_at": datetime.now(),
          }
          collection.insert_one(log_data)
          
          st.success("บันทึกข้อมูลสำเร็จเรียบร้อยแล้ว! 🎉")
          st.session_state.form_submitted = False
          st.session_state.uploader_key += 1
          st.rerun()
      else:
        st.warning("กรุณากรอกหัวข้อและรายละเอียดให้ครบถ้วนครับ")

  st.divider()
  
  # ค้นหาและกรองข้อมูล
  st.subheader("🔍 ค้นหาและกรองข้อมูลผลงานของคุณ")
  f_search_col1, f_search_col2 = st.columns([2, 1])
  with f_search_col1:
    search_keyword = st.text_input("🔎 ค้นหาจากหัวข้อหรือเนื้อหา (Keyword):", "").strip()
  with f_search_col2:
    category_options = ["ทั้งหมด", "Coding", "Meeting", "Debugging", "Learning", "Other"]
    selected_category_filter = st.selectbox("📌 กรองตามหมวดหมู่:", category_options)

  query_filter = {"author": clean_user}
  if selected_category_filter != "ทั้งหมด":
    query_filter["category"] = selected_category_filter
  if search_keyword:
    query_filter["$or"] = [
        {"title": {"$regex": search_keyword, "$options": "i"}},
        {"content": {"$regex": search_keyword, "$options": "i"}}
    ]

  # Dashboard สรุปสถิติ
  st.markdown("---")
  st.subheader("📊 แดชบอร์ดสรุปสถิติผลงานของคุณ")

  dashboard_logs = list(collection.find(query_filter))
  total_count = len(dashboard_logs)

  if total_count > 0:
    cat_counts = {}
    for item in dashboard_logs:
      c = item.get("category", "Other")
      cat_counts[c] = cat_counts.get(c, 0) + 1

    d_col1, d_col2, d_col3 = st.columns(3)
    with d_col1:
      st.metric("📌 จำนวนงานทั้งหมด (รายการ)", total_count)
    with d_col2:
      top_cat = max(cat_counts, key=cat_counts.get) if cat_counts else "-"
      st.metric("🔥 หมวดหมู่ยอดฮิต", top_cat)
    with d_col3:
      st.metric("🏷️ หมวดหมู่ที่ใช้งาน", f"{len(cat_counts)} ประเภท")

    st.markdown("**📈 สัดส่วนงานแยกตามหมวดหมู่:**")
    cat_cols = st.columns(len(cat_counts) if len(cat_counts) > 0 else 1)
    for idx, (cat_name, count_val) in enumerate(cat_counts.items()):
      with cat_cols[idx % len(cat_cols)]:
        st.info(f"**{cat_name}**\n\n {count_val} รายการ")
  else:
    st.info("💡 ไม่มีข้อมูลเพียงพอสำหรับการสรุปสถิติในเงื่อนไขนี้")

  st.markdown("---")

  # ส่วนดาวน์โหลดรายงาน (CSV & PDF)
  all_user_logs_for_export = list(collection.find(query_filter).sort("created_at", -1))
  if all_user_logs_for_export:
    col_d1, col_d2 = st.columns(2)
    
    with col_d1:
      csv_rows = ["Date,Category,Title,Content"]
      for log_item in all_user_logs_for_export:
        safe_title = log_item.get('title', '').replace('"', '""')
        safe_content = log_item.get('content', '').replace('"', '""').replace('\n', ' ')
        csv_rows.append(f"\"{log_item.get('date')}\",\"{log_item.get('category')}\",\"{safe_title}\",\"{safe_content}\"")
      
      csv_data = "\n".join(csv_rows)
      csv_bytes = ('\ufeff' + csv_data).encode('utf-8')
      
      st.download_button(
          label="📥 ดาวน์โหลดผลงานเป็น CSV",
          data=csv_bytes,
          file_name=f"work_log_filtered_{clean_user}.csv",
          mime="text/csv",
          use_container_width=True
      )

    with col_d2:
      pdf_bytes = generate_pdf_report(clean_user, all_user_logs_for_export)
      st.download_button(
          label="📄 ดาวน์โหลดรายงาน PDF",
          data=pdf_bytes,
          file_name=f"work_log_report_{clean_user}.pdf",
          mime="application/pdf",
          use_container_width=True
      )

  st.subheader("📚 รายการผลงานของคุณ")

  ITEMS_PER_PAGE = 5
  total_user_logs = collection.count_documents(query_filter)

  if total_user_logs == 0:
    st.info("ไม่พบข้อมูลผลงานที่ตรงกับเงื่อนไขการค้นหาครับ")
  else:
    total_pages = (total_user_logs + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    
    if total_pages > 1:
      current_page = st.selectbox("📄 เลือกหน้าแสดงผล", range(1, total_pages + 1), format_func=lambda x: f"หน้าที่ {x} (จากทั้งหมด {total_pages} หน้า)")
    else:
      current_page = 1
      
    skip_count = (current_page - 1) * ITEMS_PER_PAGE
    
    user_logs = list(
        collection.find(query_filter)
        .sort("created_at", -1)
        .skip(skip_count)
        .limit(ITEMS_PER_PAGE)
    )

    for log in user_logs:
      with st.expander(f"📌 [{log['category']}] {log['title']} ({log['date']})"):
        
        edit_key = f"edit_mode_{log['_id']}"
        if edit_key not in st.session_state:
          st.session_state[edit_key] = False

        if not st.session_state[edit_key]:
          st.write(f"**รายละเอียด:** {log['content']}")
          
          attachments_to_show = log.get("attachments", [])
          if not attachments_to_show and log.get("attachment"):
              attachments_to_show = [log.get("attachment")]
          
          if attachments_to_show:
            st.write("📎 **ไฟล์แนบ:**")
            for att_url in attachments_to_show:
              lower_url = att_url.lower()
              if any(ext in lower_url for ext in [".png", ".jpg", ".jpeg", ".webp"]):
                optimized_img_url = optimize_cloudinary_url(att_url, width=800)
                st.image(optimized_img_url, width=400)
              elif any(ext in lower_url for ext in [".mp4", ".mov", ".avi"]):
                st.video(att_url)
              else:
                st.markdown(f"📄 [คลิกเพื่อเปิดดูไฟล์เอกสาร]({att_url})", unsafe_allow_html=True)

          comments = log.get("comments", [])
          if comments:
            st.markdown("---")
            st.markdown("💬 **ความคิดเห็นจากผู้เยี่ยมชม:**")
            for c in comments:
              st.markdown(f"- **{c['user']}:** {c['text']} <span style='color:gray; font-size:small;'>({c['time']})</span>", unsafe_allow_html=True)

          st.markdown("---")
          col_act1, col_act2 = st.columns(2)
          with col_act1:
            if st.button("✏️ แก้ไขบันทึกนี้", key=f"btn_edit_{log['_id']}", use_container_width=True):
              if log.get("author") == clean_user:
                st.session_state[edit_key] = True
                st.rerun()
              else:
                st.error("❌ คุณไม่มีสิทธิ์แก้ไขโพสต์ของผู้อื่น!")
          with col_act2:
            if st.button("🗑️ ลบบันทึกนี้", key=f"del_{log['_id']}", type="secondary", use_container_width=True):
              delete_result = collection.delete_one({"_id": log["_id"], "author": clean_user})
              if delete_result.deleted_count > 0:
                st.success("ลบข้อมูลสำเร็จแล้ว!")
                st.rerun()
              else:
                st.error("❌ เกิดข้อผิดพลาด: คุณไม่มีสิทธิ์ลบโพสต์นี้!")

        else:
          st.markdown("#### ✏️ แก้ไขข้อมูลบันทึกงาน")
          with st.form(key=f"form_edit_{log['_id']}"):
            categories_list = ["Coding", "Meeting", "Debugging", "Learning", "Other"]
            default_cat_idx = categories_list.index(log['category']) if log['category'] in categories_list else 0
            
            e_col1, e_col2 = st.columns(2)
            with e_col1:
              try:
                default_date = datetime.strptime(log['date'], "%Y-%m-%d").date()
              except:
                default_date = datetime.today().date()
              new_date = st.date_input("วันที่ปฏิบัติงาน", default_date)
            with e_col2:
              new_category = st.selectbox("หมวดหมู่งาน", categories_list, index=default_cat_idx)
              
            new_title = st.text_input("หัวข้อเรื่อง / งานที่ทำ", value=log['title'])
            new_content = st.text_area("รายละเอียดการทำงาน", value=log['content'])

            col_sub1, col_sub2 = st.columns(2)
            with col_sub1:
              update_btn = st.form_submit_button("💾 บันทึกการแก้ไข", use_container_width=True)
            with col_sub2:
              cancel_btn = st.form_submit_button("❌ ยกเลิก", use_container_width=True)

            if update_btn:
              if new_title and new_content:
                update_result = collection.update_one(
                    {"_id": log["_id"], "author": clean_user},
                    {
                        "$set": {
                            "date": str(new_date),
                            "category": new_category,
                            "title": new_title,
                            "content": new_content,
                        }
                    }
                )
                if update_result.modified_count > 0 or update_result.matched_count > 0:
                  st.session_state[edit_key] = False
                  st.success("แก้ไขข้อมูลสำเร็จเรียบร้อยแล้ว! 🎉")
                  st.rerun()
                else:
                  st.error("❌ ไม่มีสิทธิ์แก้ไขข้อมูลนี้")
              else:
                st.warning("กรุณากรอกหัวข้อและรายละเอียดให้ครบถ้วน")

            if cancel_btn:
              st.session_state[edit_key] = False
              st.rerun()

# ==========================================
# โหมดที่ 2: เยี่ยมชมโปรไฟล์เพื่อนๆ (Explore)
# ==========================================
elif nav_mode == "🌐 หน้าเยี่ยมชมโปรไฟล์เพื่อนๆ":
  st.markdown("<div class='main-title'>🌐 พื้นที่สำรวจและเยี่ยมชมผลงานเพื่อนๆ</div>", unsafe_allow_html=True)
  st.write("เลือกดูโปรไฟล์และผลงานของเพื่อนร่วมทีม พร้อมส่งข้อความคอมเมนต์และกดไลก์ให้กำลังใจกันได้ที่นี่ครับ!")
  st.markdown("<br>", unsafe_allow_html=True)

  all_authors = collection.distinct("author")
  other_authors = [a for a in all_authors if a.lower() != clean_user.lower()]

  if len(other_authors) == 0:
    st.info("ยังไม่มีผู้ใช้งานคนอื่นในระบบเลยครับ ชวนเพื่อนมาสมัครใช้งานกันเถอะ!")
  else:
    selected_friend = st.selectbox("🔍 เลือกรายชื่อเพื่อนที่คุณต้องการเยี่ยมชม:", other_authors)
    
    if selected_friend:
      if selected_friend != clean_user:
        visitor_session_key = f"visited_{selected_friend}"
        if visitor_session_key not in st.session_state:
          st.session_state[visitor_session_key] = True
          visitor_collection.insert_one({
              "profile_owner": selected_friend,
              "visitor": clean_user,
              "visited_at": datetime.now()
          })

      st.divider()
      friend_profile = profile_collection.find_one({"author": selected_friend}) | {}
      
      f_col1, f_col2 = st.columns([1, 6])
      with f_col1:
        f_avatar = friend_profile.get("avatar", "")
        if f_avatar:
          optimized_f_avatar = optimize_cloudinary_url(f_avatar, width=200)
          st.image(optimized_f_avatar, width=120)
        else:
          st.info("🖼️ ไม่มีรูปโปรไฟล์")
      with f_col2:
        st.subheader(f"👤 โปรไฟล์ของ: {selected_friend}")
        st.write(f"**Bio:** {friend_profile.get('bio', 'ยังไม่มีคำอธิบาย')}")

      st.divider()
      
      st.subheader(f"🔍 ค้นหาผลงานของ {selected_friend}")
      f_f_col1, f_f_col2 = st.columns([2, 1])
      with f_f_col1:
        friend_search_keyword = st.text_input("🔎 ค้นหาจากหัวข้อหรือเนื้อหาของเพื่อน:", "", key="f_search").strip()
      with f_f_col2:
        friend_category_options = ["ทั้งหมด", "Coding", "Meeting", "Debugging", "Learning", "Other"]
        friend_selected_category = st.selectbox("📌 กรองตามหมวดหมู่เพื่อน:", friend_category_options, key="f_cat")

      friend_query_filter = {"author": selected_friend}
      if friend_selected_category != "ทั้งหมด":
        friend_query_filter["category"] = friend_selected_category
      if friend_search_keyword:
        friend_query_filter["$or"] = [
            {"title": {"$regex": friend_search_keyword, "$options": "i"}},
            {"content": {"$regex": friend_search_keyword, "$options": "i"}}
        ]

      st.markdown("---")
      st.subheader(f"📊 แดชบอร์ดสรุปสถิติผลงานของ {selected_friend}")

      friend_dashboard_logs = list(collection.find(friend_query_filter))
      friend_total_count = len(friend_dashboard_logs)

      if friend_total_count > 0:
        f_cat_counts = {}
        for item in friend_dashboard_logs:
          c = item.get("category", "Other")
          f_cat_counts[c] = f_cat_counts.get(c, 0) + 1

        fd_col1, fd_col2, fd_col3 = st.columns(3)
        with fd_col1:
          st.metric("📌 จำนวนงานทั้งหมดของเพื่อน", friend_total_count)
        with fd_col2:
          f_top_cat = max(f_cat_counts, key=f_cat_counts.get) if f_cat_counts else "-"
          st.metric("🔥 หมวดหมู่ยอดฮิตของเพื่อน", f_top_cat)
        with fd_col3:
          st.metric("🏷️ หมวดหมู่ที่เพื่อนใช้งาน", f"{len(f_cat_counts)} ประเภท")

        st.markdown(f"**📈 สัดส่วนงานของ {selected_friend} แยกตามหมวดหมู่:**")
        f_cat_cols = st.columns(len(f_cat_counts) if len(f_cat_counts) > 0 else 1)
        for idx, (cat_name, count_val) in enumerate(f_cat_counts.items()):
          with f_cat_cols[idx % len(f_cat_cols)]:
            st.info(f"**{cat_name}**\n\n {count_val} รายการ")
      else:
        st.info("💡 ไม่มีข้อมูลเพียงพอสำหรับการสรุปสถิติในเงื่อนไขนี้")

      st.markdown("---")
      st.subheader(f"📚 ผลงานทั้งหมดของ {selected_friend}")
      
      friend_total_logs = collection.count_documents(friend_query_filter)
      if friend_total_logs == 0:
        st.info(f"ไม่พบผลงานที่ตรงกับเงื่อนไขการค้นหาของเพื่อนคนนี้ครับ")
      else:
        friend_total_pages = (friend_total_logs + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        if friend_total_pages > 1:
          friend_current_page = st.selectbox("📄 เลือกหน้าผลงานเพื่อน", range(1, friend_total_pages + 1), format_func=lambda x: f"หน้าที่ {x} (จากทั้งหมด {friend_total_pages} หน้า)", key="friend_page_select")
        else:
          friend_current_page = 1
          
        friend_skip = (friend_current_page - 1) * ITEMS_PER_PAGE
        friend_logs = list(
            collection.find(friend_query_filter)
            .sort("created_at", -1)
            .skip(friend_skip)
            .limit(ITEMS_PER_PAGE)
        )

        for log in friend_logs:
          with st.expander(f"📌 [{log['category']}] {log['title']} ({log['date']})"):
            st.write(f"**รายละเอียด:** {log['content']}")
            
            attachments_to_show = log.get("attachments", [])
            if not attachments_to_show and log.get("attachment"):
                attachments_to_show = [log.get("attachment")]
            
            if attachments_to_show:
              st.write("📎 **ไฟล์แนบ:**")
              for att_url in attachments_to_show:
                lower_url = att_url.lower()
                if any(ext in lower_url for ext in [".png", ".jpg", ".jpeg", ".webp"]):
                  optimized_img_url = optimize_cloudinary_url(att_url, width=800)
                  st.image(optimized_img_url, width=400)
                elif any(ext in lower_url for ext in [".mp4", ".mov", ".avi"]):
                  st.video(att_url)
                else:
                  st.markdown(f"📄 [คลิกเพื่อเปิดดูไฟล์เอกสาร]({att_url})", unsafe_allow_html=True)

            likes_list = log.get("likes", [])
            total_likes = len(likes_list)
            is_liked_by_me = clean_user in likes_list

            st.markdown("---")
            col_like1, col_like2 = st.columns([1, 5])
            with col_like1:
              like_btn_label = f"❤️ {total_likes}" if is_liked_by_me else f"🤍 {total_likes}"
              if st.button(like_btn_label, key=f"like_{log['_id']}", use_container_width=True):
                if is_liked_by_me:
                  collection.update_one(
                      {"_id": log["_id"]},
                      {"$pull": {"likes": clean_user}}
                  )
                else:
                  collection.update_one(
                      {"_id": log["_id"]},
                      {"$addToSet": {"likes": clean_user}}
                  )
                st.rerun()

            comments = log.get("comments", [])
            st.markdown("💬 **ความคิดเห็นทั้งหมด:**")
            if comments:
              for c in comments:
                st.markdown(f"- **{c['user']}:** {c['text']} <span style='color:gray; font-size:small;'>({c['time']})</span>", unsafe_allow_html=True)
            else:
              st.caption("ยังไม่มีความคิดเห็น เป็นคนแรกที่คอมเมนต์เลยสิ!")

            with st.form(key=f"comment_form_{log['_id']}"):
              comment_text = st.text_input("💬 แสดงความคิดเห็น:")
              submit_comment = st.form_submit_button("ส่งคอมเมนต์", use_container_width=True)
              
              if submit_comment:
                if comment_text.strip():
                  new_comment = {
                      "user": clean_user,
                      "text": comment_text.strip(),
                      "time": datetime.now().strftime("%Y-%m-%d %H:%M")
                  }
                  collection.update_one(
                      {"_id": log["_id"]},
                      {"$push": {"comments": new_comment}}
                  )
                  st.success("ส่งคอมเมนต์เรียบร้อยแล้ว! 🚀")
                  st.rerun()
                else:
                  st.warning("กรุณาพิมพ์ข้อความคอมเมนต์ก่อนส่งครับ")
            
            st.caption("🔒 (โหมดเยี่ยมชม: คุณสามารถดู, กดไลก์ และคอมเมนต์ได้เท่านั้น)")