import hashlib
import cloudinary
import cloudinary.uploader
import pymongo
import streamlit as st

# --- ตั้งค่าการเชื่อมต่อฐานข้อมูลและ Cloudinary ---
MONGO_URI = st.secrets["MONGO_URI"]
client = pymongo.MongoClient(MONGO_URI)
db = client["worklog_db"]

user_auth_collection = db["users"]
profile_collection = db["profiles"]

# ตั้งค่า Cloudinary
cloudinary.config(
    cloud_name=st.secrets["cloudinary"]["cloud_name"],
    api_key=st.secrets["cloudinary"]["api_key"],
    api_secret=st.secrets["cloudinary"]["api_secret"],
)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

@st.cache_data(ttl=300)
def get_cached_profile(username):
    profile = profile_collection.find_one({"author": username})
    if not profile:
        return {"bio": "ยังไม่ได้เขียนอธิบายตัวเอง...", "avatar": ""}
    return profile

# --- จัดการ Session State ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""

st.set_page_config(page_title="Work Log & Profile System", page_icon="📝", layout="wide")

# --- ระบบล็อกอิน / สมัครสมาชิก ---
if not st.session_state.logged_in:
    st.title("🔐 เข้าสู่ระบบ / สมัครสมาชิก")
    tab1, tab2 = st.tabs(["🔑 เข้าสู่ระบบ", "📝 สมัครสมาชิก"])

    with tab1:
        login_user = st.text_input("ชื่อผู้ใช้งาน", key="login_user")
        login_pass = st.text_input("รหัสผ่าน", type="password", key="login_pass")
        if st.button("🚀 เข้าสู่ระบบทันที", use_container_width=True):
            user_record = user_auth_collection.find_one({"username": login_user})
            if user_record and user_record["password"] == hash_password(login_pass):
                st.session_state.logged_in = True
                st.session_state.username = login_user
                st.rerun()
            else:
                st.error("❌ ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")

    with tab2:
        reg_user = st.text_input("กำหนดชื่อผู้ใช้งาน", key="reg_user")
        reg_pass = st.text_input("กำหนดรหัสผ่าน", type="password", key="reg_pass")
        if st.button("✨ ยืนยันการสมัครสมาชิก", use_container_width=True):
            if user_auth_collection.find_one({"username": reg_user}):
                st.error("❌ ชื่อผู้ใช้นี้ถูกใช้งานแล้ว")
            else:
                user_auth_collection.insert_one({"username": reg_user, "password": hash_password(reg_pass)})
                profile_collection.insert_one({"author": reg_user, "bio": "ยังไม่ได้เขียนอธิบายตัวเอง...", "avatar": ""})
                st.success("🎉 สมัครสมาชิกสำเร็จ!")
    st.stop()

# --- ส่วนของผู้ใช้งานที่ล็อกอินแล้ว ---
clean_user = st.session_state.username
st.sidebar.markdown(f"👤 **ผู้ใช้งาน:** {clean_user}")
if st.sidebar.button("🚪 ออกจากระบบ", use_container_width=True):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("#### 🎨 ตั้งค่าโปรไฟล์ส่วนตัว")
user_profile = get_cached_profile(clean_user)

with st.sidebar.form("profile_form"):
    new_bio = st.text_area("คำอธิบายสั้นๆ (Bio):", value=user_profile.get("bio", ""))
    avatar_file = st.file_uploader("เปลี่ยนรูปโปรไฟล์", type=["png", "jpg", "jpeg"])
    confirm_pass = st.text_input("🔑 ยืนยันรหัสผ่าน", type="password")
    
    if st.form_submit_button("💾 บันทึกโปรไฟล์", use_container_width=True):
        auth_check = user_auth_collection.find_one({"username": clean_user})
        if auth_check and auth_check["password"] == hash_password(confirm_pass):
            avatar_url = user_profile.get("avatar", "")
            if avatar_file:
                upload_data = cloudinary.uploader.upload(avatar_file, folder="worklog_avatars")
                avatar_url = upload_data.get("secure_url")
            
            profile_collection.update_one({"author": clean_user}, {"$set": {"bio": new_bio, "avatar": avatar_url}}, upsert=True)
            st.success("บันทึกโปรไฟล์สำเร็จ!")
            st.rerun()
        else:
            st.error("❌ รหัสผ่านไม่ถูกต้อง")

st.title("📁 พอร์ตโฟลิโอและบันทึกงานของคุณ")
st.write(f"ยินดีต้อนรับคุณ **{clean_user}**")