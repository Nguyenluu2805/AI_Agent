import os
import re
from src import config

def parse_sections(text):
    """
    Phân tách chuỗi yeu_cau_chi_tiet chứa các thẻ như [Vấn đề hiện tại], [Yêu cầu đầu ra]...
    thành một từ điển các phần để format đẹp mắt.
    """
    sections = {}
    if not text:
        return sections
        
    # Danh sách các thẻ tag cần tìm kiếm
    tags = [
        "Vấn đề hiện tại",
        "Yêu cầu nghiệp vụ",
        "Quy tắc nghiệp vụ",
        "Quy tắc điểm danh",
        "Ràng buộc & Bẫy dữ liệu",
        "Bẫy dữ liệu",
        "Ràng buộc kỹ thuật",
        "Yêu cầu đầu ra",
        "Báo cáo phân tích",
        "Yêu cầu nộp bài"
    ]
    
    # Tạo biểu thức chính quy để phân tách các tag dạng [Tag Name] hoặc Tag Name:
    # Hỗ trợ nuốt luôn cả dấu hai chấm/gạch ngang ngay sau dấu ngoặc vuông ]
    pattern = r'(?:^|\n)\s*(?:\[(' + '|'.join(tags) + r')\]\s*[:\-]?\s*|(' + '|'.join(tags) + r')\s*[:\-]\s*)'
    
    matches = list(re.finditer(pattern, text))
    
    if not matches:
        # Nếu không khớp thẻ nào, coi toàn bộ là Yêu cầu nộp bài
        sections["Yêu cầu nộp bài"] = text.strip()
        return sections
        
    # Duyệt qua các mốc khớp để cắt chuỗi
    for i, match in enumerate(matches):
        tag_name = match.group(1) or match.group(2)
        start_idx = match.end()
        end_idx = matches[i+1].start() if i + 1 < len(matches) else len(text)
        content = text[start_idx:end_idx].strip()
        # Loại bỏ các ký tự dấu hai chấm, dấu gạch ngang dư thừa ở đầu nội dung
        content = re.sub(r'^[:\-]\s*', '', content).strip()
        sections[tag_name] = content
        
    return sections

def publish_json_to_markdown(json_data):
    """
    Chuyển đổi dữ liệu bài tập dạng JSON sang file Markdown định dạng chuẩn, trực quan.
    Tuân thủ nghiêm ngặt quy định layout mới (▪ Bối cảnh & vai trò, ▪ Quy tắc nghiệp vụ, ▪ Bẫy dữ liệu...)
    """
    try:
        chu_de = json_data.get("chu_de", "Bai_Tap")
        muc_tieu = json_data.get("muc_tieu", "Chưa có mục tiêu cụ thể.")
        danh_sach = json_data.get("danh_sach_bai_tap", [])
        subject = json_data.get("subject", "Python").capitalize()

        # Chuẩn hóa tên file an toàn
        safe_name = chu_de.replace(" ", "_").replace("-", "_")
        md_file_path = os.path.join(config.OUTPUT_MD_DIR, f"GiaoAnStandard_{safe_name}.md")

        with open(md_file_path, "w", encoding="utf-8") as md_f:
            md_f.write(f"# HỆ THỐNG BÀI TẬP VỀ NHÀ CHUẨN CHỈNH: {chu_de.upper()} ({subject.upper()})\n\n")
            md_f.write(f"### Mục tiêu buổi học:\n{muc_tieu}\n\n")
            md_f.write("---\n\n")

            for idx, bt in enumerate(danh_sach, 1):
                # 1. Ghi tiêu đề phần cấp độ bài tập
                if idx == 1:
                    md_f.write("## I. VẬN DỤNG CƠ BẢN\n\n")
                elif idx == 3:
                    md_f.write("## II. VẬN DỤNG CHUYÊN SÂU\n\n")
                elif idx == 4:
                    md_f.write("## III. PHÂN TÍCH\n\n")
                elif idx == 5:
                    md_f.write("## IV. SÁNG TẠO\n\n")

                # 2. Đánh số bài thứ tự trong phân loại
                sub_idx = idx
                if idx == 2:
                    sub_idx = 2
                elif idx >= 3:
                    sub_idx = 1

                ten_bai = bt.get('ten_bai', f'Bài tập {idx}')
                # Làm sạch chữ "Bài X:" lặp lại
                clean_ten_bai = re.sub(r'^(?:Bài\s*\d+\s*:\s*)+', '', ten_bai, flags=re.IGNORECASE).strip()
                md_f.write(f"### {sub_idx}. Bài {idx}: {clean_ten_bai}\n\n")

                # Parse nội dung yeu_cau_chi_tiet
                boi_canh = bt.get('boi_canh_nghiep_vu')
                yeu_cau = bt.get('yeu_cau_chi_tiet') or bt.get('yeu_cau')
                code_loi = bt.get('code_loi_chua_sua')
                parsed = parse_sections(yeu_cau)

                # --- MỤC 1: BỐI CẢNH & VAI TRÒ ---
                if boi_canh:
                    md_f.write(f"▪ **Bối cảnh & vai trò:**\n{boi_canh}\n\n")

                # --- MỤC 2: QUY TẮC NGHIỆP VỤ / VẤN ĐỀ HIỆN TẠI / RÀNG BUỘC KỸ THUẬT ---
                vande = parsed.get("Vấn đề hiện tại")
                if vande:
                    md_f.write(f"▪ **Vấn đề hiện tại:**\n{vande}\n\n")

                quy_tac = parsed.get("Quy tắc nghiệp vụ") or parsed.get("Yêu cầu nghiệp vụ") or parsed.get("Quy tắc điểm danh")
                if quy_tac:
                    md_f.write(f"▪ **Quy tắc nghiệp vụ:**\n{quy_tac}\n\n")

                ky_thuat = parsed.get("Ràng buộc kỹ thuật")
                if ky_thuat:
                    md_f.write(f"▪ **Ràng buộc kỹ thuật:**\n{ky_thuat}\n\n")

                # --- MỤC 3: HIỆN TRƯỜNG GIẢ (CODE LỖI) ---
                if code_loi:
                    cleaned_code = code_loi.strip()
                    # Làm sạch dấu backticks thừa
                    if cleaned_code.startswith("```") or cleaned_code.strip().startswith("```"):
                        lines = cleaned_code.splitlines()
                        if lines and lines[0].strip().startswith("```"):
                            lines = lines[1:]
                        if lines and lines[-1].strip().startswith("```"):
                            lines = lines[:-1]
                        cleaned_code = "\n".join(lines)
                    md_f.write("▪ **Hiện trường giả (Source code lỗi):**\n")
                    md_f.write("```python\n")
                    md_f.write(f"{cleaned_code}\n")
                    md_f.write("```\n\n")

                # --- MỤC 4: BẪY DỮ LIỆU ---
                bay = parsed.get("Ràng buộc & Bẫy dữ liệu") or parsed.get("Bẫy dữ liệu")
                if bay:
                    md_f.write(f"▪ **Bẫy dữ liệu:**\n{bay}\n\n")

                # --- MỤC 5: YÊU CẦU NỘP BÀI ---
                nop = parsed.get("Yêu cầu đầu ra") or parsed.get("Yêu cầu nộp bài") or parsed.get("Báo cáo phân tích")
                if nop:
                    md_f.write(f"▪ **Yêu cầu nộp bài:**\n{nop}\n\n")



                md_f.write("---\n\n")

        print(f"  [Dong goi] Da xuat ban va dinh dang file giao an Markdown thanh cong tai:\n  {md_file_path}")
        return md_file_path
    except Exception as e:
        print(f"  [Loi] khi dong goi xuat ban file giao an: {str(e)}")
        return None

def publish_reading_to_markdown(json_data):
    """
    Chuyển đổi dữ liệu bài đọc dạng JSON sang file Markdown định dạng chuẩn, không dùng emoji.
    Tuân thủ cấu trúc 7 phần bắt buộc với ký tự La Mã (I đến VII) và tiêu đề hấp dẫn tùy chọn.
    """
    try:
        chu_de = json_data.get("chu_de", "Chu_De_Bai_Doc")
        subject = json_data.get("subject", "Python").capitalize()
        
        # Lấy tiêu đề và nội dung các phần
        dat_van_de_tieu_de = json_data.get("dat_van_de_tieu_de", "Đặt vấn đề").strip()
        dat_van_de_noi_dung = json_data.get("dat_van_de_noi_dung", json_data.get("dat_van_de", "")).strip()
        
        phan_tich_tieu_de = json_data.get("phan_tich_tieu_de", "Phân tích").strip()
        phan_tich_noi_dung = json_data.get("phan_tich_noi_dung", json_data.get("phan_tich", "")).strip()
        
        gioi_thieu_giai_phap_tieu_de = json_data.get("gioi_thieu_giai_phap_tieu_de", "Giới thiệu giải pháp").strip()
        gioi_thieu_giai_phap_noi_dung = json_data.get("gioi_thieu_giai_phap_noi_dung", json_data.get("gioi_thieu_giai_phap", "")).strip()
        
        vi_du_minh_hoa_tieu_de = json_data.get("vi_du_minh_hoa_tieu_de", "Ví dụ minh họa").strip()
        vi_du_minh_hoa_noi_dung = json_data.get("vi_du_minh_hoa_noi_dung", json_data.get("vi_du_minh_hoa", "")).strip()
        
        giai_quyet_van_de_tieu_de = json_data.get("giai_quyet_van_de_tieu_de", "Giải quyết vấn đề").strip()
        giai_quyet_van_de_noi_dung = json_data.get("giai_quyet_van_de_noi_dung", json_data.get("giai_quyet_van_de", "")).strip()
        
        tong_ket_luu_y_tieu_de = json_data.get("tong_ket_luu_y_tieu_de", "Tổng kết và lưu ý").strip()
        tong_ket_luu_y_noi_dung = json_data.get("tong_ket_luu_y_noi_dung", json_data.get("tong_ket_luu_y", "")).strip()
        
        bo_cau_hoi = json_data.get("bo_cau_hoi_kiem_tra", [])
        
        # Chuẩn hóa tên file an toàn
        safe_name = chu_de.replace(" ", "_").replace("-", "_")
        md_file_path = os.path.join(config.OUTPUT_MD_DIR, f"GiaoAnStandard_Reading_{safe_name}.md")
        
        with open(md_file_path, "w", encoding="utf-8") as md_f:
            md_f.write(f"# BÀI ĐỌC CHI TIẾT: {chu_de.upper()} ({subject.upper()})\n\n")
            md_f.write("---\n\n")
            
            # I. Đặt vấn đề
            md_f.write(f"## I. {dat_van_de_tieu_de}\n\n")
            md_f.write(f"{dat_van_de_noi_dung}\n\n")
            md_f.write("---\n\n")
            
            # II. Phân tích
            md_f.write(f"## II. {phan_tich_tieu_de}\n\n")
            md_f.write(f"{phan_tich_noi_dung}\n\n")
            md_f.write("---\n\n")
            
            # III. Giới thiệu giải pháp
            md_f.write(f"## III. {gioi_thieu_giai_phap_tieu_de}\n\n")
            md_f.write(f"{gioi_thieu_giai_phap_noi_dung}\n\n")
            md_f.write("---\n\n")
            
            # IV. Ví dụ minh họa
            md_f.write(f"## IV. {vi_du_minh_hoa_tieu_de}\n\n")
            if vi_du_minh_hoa_noi_dung:
                cleaned_code = vi_du_minh_hoa_noi_dung.strip()
                if cleaned_code.startswith("```") or cleaned_code.strip().startswith("```"):
                    lines = cleaned_code.splitlines()
                    if lines and lines[0].strip().startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].strip().startswith("```"):
                        lines = lines[:-1]
                    cleaned_code = "\n".join(lines)
                
                # Xác định ngôn ngữ highlight
                lang_code = "java" if "java" in subject.lower() else "python"
                md_f.write(f"```{lang_code}\n{cleaned_code}\n```\n\n")
            md_f.write("---\n\n")
            
            # V. Giải quyết vấn đề
            md_f.write(f"## V. {giai_quyet_van_de_tieu_de}\n\n")
            if giai_quyet_van_de_noi_dung:
                cleaned_code = giai_quyet_van_de_noi_dung.strip()
                if cleaned_code.startswith("```") or cleaned_code.strip().startswith("```"):
                    lines = cleaned_code.splitlines()
                    if lines and lines[0].strip().startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].strip().startswith("```"):
                        lines = lines[:-1]
                    cleaned_code = "\n".join(lines)
                
                if "\n" in cleaned_code and ("def " in cleaned_code or "print(" in cleaned_code or "class " in cleaned_code or "public class " in cleaned_code or "import " in cleaned_code):
                    lang_code = "java" if "java" in subject.lower() else "python"
                    md_f.write(f"```{lang_code}\n{cleaned_code}\n```\n\n")
                else:
                    md_f.write(f"{giai_quyet_van_de_noi_dung}\n\n")
            md_f.write("---\n\n")
            
            # VI. Tổng kết và lưu ý
            md_f.write(f"## VI. {tong_ket_luu_y_tieu_de}\n\n")
            md_f.write(f"{tong_ket_luu_y_noi_dung}\n\n")
            md_f.write("---\n\n")
            
            # VII. Bộ câu hỏi kiểm tra
            md_f.write("## VII. Câu hỏi kiểm tra độ hiểu của bài đọc\n\n")
            if bo_cau_hoi:
                if isinstance(bo_cau_hoi, list):
                    for i, q in enumerate(bo_cau_hoi, 1):
                        clean_q = re.sub(r'^(?:Câu\s*\d+\s*:\s*)+', '', q, flags=re.IGNORECASE).strip()
                        clean_q = re.sub(r'^(?:\*\*(?:Thông hiểu|Vận dụng|Phân tích)\*\*:\s*)+', '', clean_q, flags=re.IGNORECASE).strip()
                        
                        level_label = ""
                        if i == 1:
                            level_label = "Thông hiểu"
                        elif i == 2:
                            level_label = "Vận dụng"
                        elif i == 3:
                            level_label = "Phân tích"
                            
                        md_f.write(f"* **Câu {i} ({level_label}):** {clean_q}\n")
                else:
                    md_f.write(f"{bo_cau_hoi}\n")
            md_f.write("\n")

        print(f"  [Dong goi] Da xuat ban va dinh dang file bai doc Markdown thanh cong tai:\n  {md_file_path}")
        return md_file_path
    except Exception as e:
        print(f"  [Loi] khi dong goi xuat ban file bai doc: {str(e)}")
        return None
