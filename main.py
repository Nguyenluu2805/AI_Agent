import os
import sys
from src.database.chroma_client import RikkeiChromaClient
from src.agents.rikkei_agent import RikkeiAgent

def main():
    # Khởi tạo các thành phần hệ thống
    db_client = RikkeiChromaClient()
    agent = RikkeiAgent(chroma_client=db_client)

    print("=======================================================================")
    print("HE THONG HO TRO DAO TAO RIKKEI - TU DONG HOA TOAN DIEN")
    print("=======================================================================")

    # 1. Tự động đồng bộ hóa tài liệu tri thức đầu vào
    print("[He thong] Dang tu dong dong bo hoa tai lieu tri thuc...")
    db_client.run_sync()
    print("[He thong] Dong bo hoa hoan tat.\n")

    # 2. Lấy chủ đề bài tập từ tham số dòng lệnh hoặc từ người dùng
    if len(sys.argv) > 1:
        user_input = sys.argv[1].strip()
        print(f"Nhan yeu cau tu tham so dòng lenh: '{user_input}'")
    else:
        user_input = input("Nhap yeu cau thiet ke bai tap (vi du: String, Mang va List...): ").strip()
        
    if not user_input:
        print("[Loi] Yeu cau khong duoc de trong.")
        sys.exit(1)

    is_reading = "bài đọc" in user_input.lower() or "reading" in user_input.lower()
    type_label = "bai doc" if is_reading else "bai tap"
    print(f"\n[He thong] Dang thuc hien thiet ke {type_label} cho chu de: '{user_input}'...")
    response = agent.run_agent(user_input)

    if response:
        print("\n--- PHAN HOI CUOI CUNG CUA AGENT ---")
        print(response)
        print("-----------------------------------")
    else:
        print("  [Loi] That bai khi van hanh Agent. Vui long kiem tra ket noi Ollama local.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[He thong] Dong chuong trinh dot ngot. Tam biet!")
        sys.exit(0)
