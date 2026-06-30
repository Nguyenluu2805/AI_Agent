import json
import os
# pyrefly: ignore [missing-import]
import ollama
# pyrefly: ignore [missing-import]
import chromadb
from src import config
from src.agents.base import BaseAgent
from src.database.chroma_client import RikkeiChromaClient
from src.services.rikkei_api import RikkeiPortalAPI
from src.utils.publisher import publish_json_to_markdown, publish_reading_to_markdown

class RikkeiAgent(BaseAgent):
    """
    Agent chuyên môn hóa cho Rikkei Portal:
    Sử dụng cơ chế ReAct (Reasoning and Acting) tự trị bằng cấu trúc JSON
    tích hợp bộ lọc Metadata ChromaDB và vòng lặp tự kiểm duyệt (Reflection Loop) kết hợp mã nguồn cứng và LLM.
    """
    def __init__(self, chroma_client: RikkeiChromaClient, model_name=config.MODEL_NAME):
        super().__init__(model_name)
        self.chroma_client = chroma_client
        self.api_service = RikkeiPortalAPI()
        
        self.system_instruction = (
            "Bạn là một Trợ lý AI chuyên trách đào tạo tại Rikkei Academy.\n"
            "Nhiệm vụ của bạn là hỗ trợ biên soạn học liệu bao gồm Hệ thống bài tập về nhà (Homework) hoặc Bài đọc chuyên môn (Reading) dựa trên bối cảnh tri thức.\n\n"
            "QUY ĐỊNH ĐỊNH DẠNG PHẢN HỒI:\n"
            "Mỗi lượt phản hồi, bạn BẮT BUỘC phải trả về định dạng JSON thuần túy theo cấu trúc sau:\n"
            "{\n"
            '  "thought": "Mô tả suy nghĩ hiện tại của bạn và bước tiếp theo sẽ thực hiện",\n'
            '  "action": "tên_công_cụ_muốn_gọi",\n'
            '  "arguments": { ... các tham số truyền cho công cụ tương ứng ... }\n'
            "}\n\n"
            "DANH SÁCH CÁC CÔNG CỤ (TOOLS) BẠN CÓ THỂ GỌI:\n"
            "1. `retrieve_knowledge(query: str, category: str, subject: str)`:\n"
            "   - Tìm kiếm tri thức trong Vector DB kèm bộ lọc môn học.\n"
            "   - Các tham số:\n"
            "     * `query` (từ khóa tìm kiếm)\n"
            "     * `category` ('syllabuses' cho lý thuyết giáo án hoặc 'standards' cho quy chuẩn học liệu)\n"
            "     * `subject` ('python', 'java' hoặc 'web' để lọc chính xác môn học cần tìm kiếm)\n"
            "2. `publish_homework_markdown(homework_json: dict)`:\n"
            "   - Đóng gói và xuất bản file Markdown từ cấu trúc bài tập JSON.\n"
            "   - Tham số: `homework_json` chứa thông tin bài tập (subject, chu_de, muc_tieu, danh_sach_bai_tap).\n"
            "3. `publish_reading_markdown(reading_json: dict)`:\n"
            "   - Đóng gói và xuất bản file Markdown từ cấu trúc bài đọc JSON.\n"
            "   - Bài đọc của bạn sẽ được KIỂM DUYỆT nghiêm ngặt bởi Trưởng bộ môn dựa trên nội dung tệp quy chuẩn thực tế.\n"
            "   - Tham số: `reading_json` có cấu trúc như sau:\n"
            "     {\n"
            '       "subject": "môn học chữ thường (\'python\', \'java\' hoặc \'web\')",\n'
            '       "chu_de": "tên chủ đề chính của bài học",\n'
            '       "dat_van_de_tieu_de": "tiêu đề phần đặt vấn đề",\n'
            '       "dat_van_de_noi_dung": "nội dung tình huống lỗi thực tế hoặc bối cảnh dẫn dắt",\n'
            '       "phan_tich_tieu_de": "tiêu đề phần phân tích nguyên nhân",\n'
            '       "phan_tich_noi_dung": "giải thích lý do tại sao lỗi xảy ra và tại sao giải pháp thông thường thất bại",\n'
            '       "gioi_thieu_giai_phap_tieu_de": "tiêu đề phần giới thiệu công nghệ mới",\n'
            '       "gioi_thieu_giai_phap_noi_dung": "giới thiệu cú pháp câu lệnh/lý thuyết giải pháp mới",\n'
            '       "vi_du_minh_hoa_tieu_de": "tiêu đề phần ví dụ minh họa",\n'
            '       "vi_du_minh_hoa_noi_dung": "khối code mẫu sạch (clean code) có chú thích rõ ràng từng dòng",\n'
            '       "giai_quyet_van_de_tieu_de": "tiêu đề phần sửa lỗi triệt để",\n'
            '       "giai_quyet_van_de_noi_dung": "áp dụng chính cú pháp mới vừa học để viết code sửa triệt để lỗi ở phần dat_van_de",\n'
            '       "tong_ket_luu_y_tieu_de": "tiêu đề phần tổng kết và lưu ý",\n'
            '       "tong_ket_luu_y_noi_dung": "tóm tắt ngắn gọn kiến thức và các lỗi thường gặp",\n'
            '       "bo_cau_hoi_kiem_tra": [\n'
            '         "Câu 1: Câu hỏi tự luận kiểm tra mức độ thông hiểu (hiểu bản chất/tại sao dùng)",\n'
            '         "Câu 2: Câu hỏi tự luận kiểm tra mức độ vận dụng (dự đoán kết quả đoạn code)",\n'
            '         "Câu 3: Câu hỏi tự luận kiểm tra mức độ phân tích (xử lý tình huống lỗi/phát hiện lỗi logic)"\n'
            '       ]\n'
            "     }\n"
            "4. `fetch_rikkei_systems()`:\n"
            "   - [TẠM THỜI KHÔNG DÙNG] Lấy danh sách các Hệ đào tạo.\n"
            "5. `sync_homework_to_rikkei(homework_json: dict)`:\n"
            "   - [TẠM THỜI KHÔNG DÙNG] Đồng bộ lên Rikkei Portal.\n"
            "6. `final_answer(response: str)`:\n"
            "   - Trả lời trực tiếp cho người dùng sau khi đã hoàn tất toàn bộ các bước hành động cần thiết.\n"
            "   - Tham số: `response` (nội dung phản hồi hoàn thành nhiệm vụ gửi người dùng).\n\n"
            "LUỒNG VẬN HÀNH BẮT BUỘC:\n"
            "- Bước 1 (Truy vấn quy chuẩn): Bạn BẮT BUỘC gọi `retrieve_knowledge` với category='standards' và subject tương ứng môn học để đọc các quy định xây dựng bài học hoặc bài tập.\n"
            "- Bước 2 (Truy vấn giáo án): Gọi `retrieve_knowledge` với category='syllabuses' để tìm giáo trình lý thuyết môn học. Nếu giáo trình không tồn tại, tự lập luận nội dung chuyên môn dựa trên kiến thức nền nhưng sản phẩm vẫn phải đạt chuẩn 100% theo tiêu chuẩn ở bước 1.\n"
            "- Bước 3 (Soạn thảo & Đóng gói):\n"
            "  * Nếu yêu cầu là soạn Bài tập (Homework): Thiết kế bộ bài tập gồm đúng 5 bài và gọi công cụ `publish_homework_markdown` với cấu trúc `homework_json` thích hợp (Bài 1&2 cơ bản có code lỗi mẫu, bài 3, 4, 5 nâng cao có báo cáo phân tích/đa giải pháp/kiến trúc; cấm luật HOW; bối cảnh đồng nhất; bẫy dữ liệu).\n"
            "  * Nếu yêu cầu là soạn Bài đọc (Reading): Thiết kế bài đọc Storytelling in Tech gồm đúng 7 phần bắt buộc và gọi công cụ `publish_reading_markdown` với cấu trúc `reading_json` chi tiết bên trên. Đảm bảo ngôn ngữ gần gũi, code mẫu sạch sẽ có highlight syntax.\n"
            "- Bước 4 (Hoàn tất): Nếu công cụ trả về APPROVED, gọi công cụ `final_answer` để thông báo đường dẫn file Markdown cho người dùng và kết thúc nhiệm vụ. Nếu trả về REJECTED, tự sửa đổi theo feedback lỗi và gọi lại công cụ xuất bản tương ứng."
        )

        # Bản đồ ánh xạ gọi hàm Python
        self.tools_map = {
            'retrieve_knowledge': self._tool_retrieve_knowledge,
            'publish_homework_markdown': self._tool_publish_homework_markdown,
            'publish_reading_markdown': self._tool_publish_reading_markdown,
            'fetch_rikkei_systems': self._tool_fetch_rikkei_systems,
            'sync_homework_to_rikkei': self._tool_sync_homework_to_rikkei
        }

    # --- IMPLEMENTATION CỦA CÁC CÔNG CỤ CỤ THỂ ---

    def _tool_retrieve_knowledge(self, query, category, subject=None):
        print(f"   [ChromaDB Tool] Dang luc tim boi canh '{query}' tai tu '{category}' (Loc mon hoc: {subject})...")
        
        # Xây dựng bộ lọc Metadata where
        where_filter = {}
        if subject:
            where_filter["subject"] = subject.lower()

        if category == 'standards':
            res = self.chroma_client.col_standards.query(
                query_texts=[query], 
                n_results=1,
                where=where_filter if where_filter else None
            )
        else:
            res = self.chroma_client.col_syllabuses.query(
                query_texts=[query], 
                n_results=1,
                where=where_filter if where_filter else None
            )

        if res and res.get('documents') and len(res['documents']) > 0 and len(res['documents'][0]) > 0:
            context = res['documents'][0][0]
            print(f"   [ChromaDB Tool] Tim thay tri thuc lien quan ({len(context)} ky tu).")
            return context
        print("   [ChromaDB Tool] Khong tim thay du lieu lien quan phu hop.")
        return f"Không có tri thức cụ thể nào về danh mục '{category}' môn '{subject}' trong Vector DB."

    def _validate_homework_structure(self, homework_json):
        """
        Kiểm duyệt cứng bằng code Python để đảm bảo cấu trúc bài tập đạt chuẩn Rikkei Academy 100%.
        """
        danh_sach = homework_json.get("danh_sach_bai_tap", [])
        if len(danh_sach) != 5:
            return f"Số lượng bài tập không đúng. Tiêu chuẩn yêu cầu đúng 5 bài tập, hiện tại có {len(danh_sach)} bài."

        levels_expected = [
            "vận dụng cơ bản",
            "vận dụng cơ bản",
            "vận dụng chuyên sâu",
            "phân tích",
            "sáng tạo"
        ]
        
        # 1. Kiểm tra cấp độ
        for idx, bt in enumerate(danh_sach):
            muc_do = bt.get("muc_do", "").lower()
            expected = levels_expected[idx]
            if expected not in muc_do:
                return f"Bài {idx+1} sai mức độ phân hóa. Kỳ vọng chứa '{expected}', thực tế là '{muc_do}'."

        # 2. Kiểm tra bài 1 & 2 bắt buộc có code lỗi mẫu
        for idx in [0, 1]:
            bt = danh_sach[idx]
            code_loi = (bt.get("code_loi_chua_sua") or "").strip()
            if not code_loi:
                return f"Bài {idx+1} (Vận dụng cơ bản) bắt buộc phải cung cấp mã nguồn lỗi mẫu trong trường 'code_loi_chua_sua' để sinh viên vá lỗi. Hãy sinh một đoạn code Python chạy được nhưng có lỗi logic hoặc thiếu điều kiện chặn lỗi."

        # 3. Kiểm tra các tiêu đề bắt buộc trong yeu_cau_chi_tiet
        for idx, bt in enumerate(danh_sach, 1):
            yeu_cau = bt.get("yeu_cau_chi_tiet", "")
            yeu_cau_lower = yeu_cau.lower()
            if idx in (1, 2):
                if "vấn đề hiện tại" not in yeu_cau_lower or "yêu cầu đầu ra" not in yeu_cau_lower:
                    return (
                        f"Bài {idx} (Vận dụng cơ bản) thiếu thẻ cấu trúc bắt buộc 'Vấn đề hiện tại' hoặc 'Yêu cầu đầu ra' trong yeu_cau_chi_tiet. "
                        "Hãy thiết lập đúng dạng:\n"
                        "[Vấn đề hiện tại]: Khách hàng phàn nàn là...\n\n"
                        "[Yêu cầu đầu ra]: 1. Chỉ ra đoạn code sai bằng dữ liệu test case. 2. Source code đã sửa."
                    )
            elif idx == 3:
                has_rules = "yêu cầu nghiệp vụ" in yeu_cau_lower or "quy tắc nghiệp vụ" in yeu_cau_lower or "quy tắc điểm danh" in yeu_cau_lower
                has_traps = "bẫy dữ liệu" in yeu_cau_lower or "ràng buộc & bẫy dữ liệu" in yeu_cau_lower
                has_output = "yêu cầu đầu ra" in yeu_cau_lower or "yêu cầu nộp bài" in yeu_cau_lower
                if not has_rules or not has_traps or not has_output:
                    return (
                        f"Bài {idx} (Vận dụng chuyên sâu) thiếu thẻ cấu trúc bắt buộc 'Yêu cầu nghiệp vụ', 'Ràng buộc & Bẫy dữ liệu' hoặc 'Yêu cầu đầu ra' trong yeu_cau_chi_tiet. "
                        "Hãy thiết lập đúng dạng:\n"
                        "[Yêu cầu nghiệp vụ]: Quy tắc hệ thống...\n\n"
                        "[Ràng buộc & Bẫy dữ liệu]: Kịch bản dữ liệu dị biệt...\n\n"
                        "[Yêu cầu đầu ra]: 1. Báo cáo phân tích và thiết kế giải pháp (Phân tích bài toán I/O, ý tưởng, lưu đồ/mã giả). 2. Triển khai code và chống lỗi."
                    )
                if "phân tích" not in yeu_cau_lower and "thiết kế" not in yeu_cau_lower:
                    return f"Bài 3 (Vận dụng chuyên sâu) thiếu yêu cầu học viên nộp 'Báo cáo phân tích' hoặc 'thiết kế giải pháp' trong phần 'Yêu cầu đầu ra'."
            elif idx == 4:
                has_rules = "quy tắc nghiệp vụ" in yeu_cau_lower or "yêu cầu nghiệp vụ" in yeu_cau_lower
                has_traps = "bẫy dữ liệu" in yeu_cau_lower or "ràng buộc & bẫy dữ liệu" in yeu_cau_lower
                has_output = "yêu cầu đầu ra" in yeu_cau_lower or "yêu cầu nộp bài" in yeu_cau_lower
                if not has_rules or not has_traps or not has_output:
                    return (
                        f"Bài 4 (Phân tích) thiếu thẻ cấu trúc bắt buộc 'Quy tắc nghiệp vụ', 'Ràng buộc & Bẫy dữ liệu' hoặc 'Yêu cầu đầu ra' trong yeu_cau_chi_tiet. "
                        "Hãy thiết lập đúng dạng:\n"
                        "[Quy tắc nghiệp vụ]: Điều kiện tính toán...\n\n"
                        "[Ràng buộc & Bẫy dữ liệu]: Kịch bản ngoại lệ...\n\n"
                        "[Yêu cầu đầu ra]: 1. Phân tích & Đề xuất (Đa giải pháp, I/O). 2. So sánh & Lựa chọn (Bảng so sánh ưu nhược trade-off, chốt chọn 1). 3. Thiết kế & Triển khai."
                    )
                if "giải pháp" not in yeu_cau_lower or "so sánh" not in yeu_cau_lower:
                    return f"Bài 4 (Phân tích) thiếu yêu cầu học viên đề xuất 'Đa giải pháp' hoặc lập bảng 'So sánh/Lựa chọn' trong phần 'Yêu cầu đầu ra'."
            elif idx == 5:
                has_tech = "ràng buộc kỹ thuật" in yeu_cau_lower or "giới hạn công nghệ" in yeu_cau_lower
                has_output = "yêu cầu đầu ra" in yeu_cau_lower or "yêu cầu nộp bài" in yeu_cau_lower
                if not has_tech or not has_output:
                    return (
                        f"Bài 5 (Sáng tạo) thiếu thẻ cấu trúc bắt buộc 'Ràng buộc kỹ thuật' hoặc 'Yêu cầu đầu ra' trong yeu_cau_chi_tiet. "
                        "Hãy thiết lập đúng dạng:\n"
                        "[Ràng buộc kỹ thuật]: Giới hạn công nghệ...\n\n"
                        "[Yêu cầu đầu ra]: 1. Thiết kế kiến trúc (Module, data flow). 2. Sản phẩm hoàn chỉnh (Code xử lý mượt mọi ngoại lệ)."
                    )
                if "kiến trúc" not in yeu_cau_lower and "module" not in yeu_cau_lower and "data flow" not in yeu_cau_lower:
                    return f"Bài 5 (Sáng tạo) thiếu yêu cầu học viên nộp 'Thiết kế kiến trúc' hoặc mô tả 'luồng dữ liệu' trong phần 'Yêu cầu đầu ra'."

        # 4. Kiểm tra nguyên tắc Đóng HOW (Cấm chỉ dẫn thuật toán trong đề bài)
        forbidden_phrases = [
            "sử dụng hàm split", "sử dụng hàm join", "sử dụng hàm strip", "sử dụng hàm replace", "sử dụng hàm sort",
            "dùng hàm split", "dùng hàm join", "dùng hàm strip", "dùng hàm replace", "dùng hàm sort", "dùng hàm pop",
            "sử dụng vòng lặp for", "sử dụng vòng lặp while", "sử dụng câu lệnh if", "dùng vòng lặp"
        ]
        for idx, bt in enumerate(danh_sach, 1):
            yeu_cau = bt.get("yeu_cau_chi_tiet", "").lower()
            for phrase in forbidden_phrases:
                if phrase in yeu_cau:
                    return f"Bài {idx} vi phạm quy tắc Đóng HOW: Đề bài không được hướng dẫn giải thuật chi tiết (Phát hiện cụm từ cấm: '{phrase}'). Hãy mô tả WHAT/WHY và yêu cầu sinh viên tự chọn thuật toán."

        return None

    def _validate_reading_structure(self, reading_json):
        """
        Kiểm duyệt cứng cấu trúc bài đọc chuẩn chỉnh bằng code Python.
        """
        if not isinstance(reading_json, dict):
            return "Dữ liệu bài đọc truyền vào không phải là một Dictionary JSON."

        subject = reading_json.get("subject")
        chu_de = reading_json.get("chu_de")
        if not subject or not chu_de:
            return "Thiếu thông tin môn học ('subject') hoặc chủ đề chính ('chu_de') của bài đọc."

        # Kiểm tra các phần tiêu đề và nội dung
        required_sections = {
            "dat_van_de": "Đặt vấn đề",
            "phan_tich": "Phân tích",
            "gioi_thieu_giai_phap": "Giới thiệu giải pháp",
            "vi_du_minh_hoa": "Ví dụ minh họa",
            "giai_quyet_van_de": "Giải quyết vấn đề",
            "tong_ket_luu_y": "Tổng kết và lưu ý"
        }
        for prefix, label in required_sections.items():
            tieu_de = reading_json.get(f"{prefix}_tieu_de", "").strip()
            noi_dung = reading_json.get(f"{prefix}_noi_dung", "").strip()
            if not tieu_de or not noi_dung:
                return f"Bài đọc bị thiếu tiêu đề hoặc nội dung phần bắt buộc: '{label}' (yêu cầu các trường '{prefix}_tieu_de' và '{prefix}_noi_dung')."

        # Kiểm tra ví dụ minh họa bắt buộc phải có code mẫu
        vi_du = reading_json.get("vi_du_minh_hoa_noi_dung", "")
        if "def " not in vi_du and "print(" not in vi_du and "class " not in vi_du and "public class " not in vi_du and "import " not in vi_du and "```" not in vi_du:
            return "Phần 'Ví dụ minh họa' (vi_du_minh_hoa_noi_dung) phải chứa mã nguồn minh họa rõ ràng."

        # Kiểm tra bộ câu hỏi kiểm tra
        bo_cau_hoi = reading_json.get("bo_cau_hoi_kiem_tra", [])
        if not isinstance(bo_cau_hoi, list):
            return "Trường 'bo_cau_hoi_kiem_tra' phải là một danh sách (List) chứa đúng 3 câu hỏi."
        if len(bo_cau_hoi) != 3:
            return f"Số lượng câu hỏi kiểm tra không đúng. Yêu cầu đúng 3 câu, hiện tại có {len(bo_cau_hoi)} câu."

        # Kiểm tra mức độ của từng câu hỏi
        q1, q2, q3 = bo_cau_hoi[0].lower(), bo_cau_hoi[1].lower(), bo_cau_hoi[2].lower()
        if "thông hiểu" not in q1 and "bản chất" not in q1 and "tại sao" not in q1 and "hiểu" not in q1:
            return "Câu hỏi 1 (bo_cau_hoi_kiem_tra[0]) phải thuộc mức độ Thông hiểu (hỏi về bản chất/tại sao dùng)."
        if "vận dụng" not in q2 and "đoạn code" not in q2 and "kết quả" not in q2 and "dự đoán" not in q2:
            return "Câu hỏi 2 (bo_cau_hoi_kiem_tra[1]) phải thuộc mức độ Vận dụng (yêu cầu dự đoán kết quả đoạn code/chạy thử code)."
        if "phân tích" not in q3 and "tình huống lỗi" not in q3 and "lỗi" not in q3 and "sửa" not in q3 and "khắc phục" not in q3:
            return "Câu hỏi 3 (bo_cau_hoi_kiem_tra[2]) phải thuộc mức độ Phân tích (xử lý tình huống lỗi/phát hiện lỗi logic)."

        return None

    def _tool_publish_reading_markdown(self, reading_json):
        try:
            chu_de = reading_json.get("chu_de", "Bai_Doc")
            subject = reading_json.get("subject", "python").lower()
            print(f"   [Publisher Tool] Tiến hành gửi bài đọc học phần '{chu_de}' qua vòng lặp kiểm duyệt (Reflection Loop) môn '{subject}'...")
            
            # --- 1. KIỂM DUYỆT CỨNG BẰNG PYTHON (PROGRAMMATIC VALIDATION) ---
            validation_error = self._validate_reading_structure(reading_json)
            if validation_error:
                print(f"   [Programmatic Validation] Kiem duyet THAT BAI: {validation_error}")
                return f"Lỗi kiểm duyệt chất lượng (REJECTED): {validation_error} Vui lòng tự sửa đổi bài đọc cho đúng quy chuẩn và gọi lại công cụ này."
            
            print("   [Programmatic Validation] Kiem duyet cau truc thanh cong.")
            
            # --- 2. ĐỌC QUY CHUẨN ĐỂ LLM SUPERVISOR KIỂM DUYỆT SÂU ---
            standards_context = ""
            try:
                standards_dir = os.path.join(config.DIR_STANDARDS, subject.capitalize())
                if os.path.exists(standards_dir):
                    contents = []
                    for f_name in os.listdir(standards_dir):
                        if f_name.endswith(('.txt', '.md')):
                            with open(os.path.join(standards_dir, f_name), "r", encoding="utf-8") as sf:
                                contents.append(sf.read())
                    if contents:
                        standards_context = "\n\n".join(contents)
                        print(f"   [Publisher Tool] Da doc truc tiep quy chuan tu o cung ({len(standards_context)} ky tu).")
            except Exception as fe:
                print(f"   [Publisher Tool] Loi doc quy chuan truc tiep: {fe}")

            if not standards_context:
                try:
                    res = self.chroma_client.col_standards.query(
                        query_texts=["Quy định xây dựng hệ thống bài học bài đọc"],
                        n_results=10,
                        where={"subject": subject}
                    )
                    if res and res.get('documents') and len(res['documents']) > 0:
                        standards_context = "\n\n".join(res['documents'][0])
                        print(f"   [Publisher Tool] Da tai quy chuan du phong tu Vector DB ({len(standards_context)} ky tu).")
                except Exception as dbe:
                    print(f"   [ChromaDB Warning] Loi khi truy van quy chuan du phong: {dbe}")
            
            if not standards_context:
                standards_context = (
                    "Quy chuẩn bài đọc bắt buộc:\n"
                    "1. Phải tuân thủ nguyên tắc Storytelling in Tech, không liệt kê định nghĩa khô khan.\n"
                    "2. Gồm đủ 7 phần: Đặt vấn đề, Phân tích, Giới thiệu giải pháp, Ví dụ minh họa, Giải quyết vấn đề, Tổng kết lưu ý, 3 câu hỏi tự luận theo 3 mức độ (thông hiểu, vận dụng, phân tích)."
                )

            # --- VÒNG LẶP KIỂM DUYỆT CHẤT LƯỢNG (REFLECTION LOOP) ---
            evaluation_instruction = (
                "Bạn là một Trưởng bộ môn kiểm định chất lượng học liệu chuyên nghiệp tại Rikkei Academy.\n"
                "Nhiệm vụ của bạn là đánh giá chất lượng bài đọc chuyên môn do AI Agent thiết kế sau đây.\n\n"
                "Bạn BẮT BUỘC phải đối chiếu kỹ lượng bài đọc với Tài liệu Quy chuẩn học liệu được cung cấp dưới đây.\n\n"
                f"--- TÀI LIỆU QUY CHUẨN KIỂM ĐỊNH ---\n{standards_context}\n--------------------------------------\n\n"
                "Các điểm kiểm tra cốt lõi bắt buộc (NẾU BÀI ĐỌC KHÔNG ĐÁP ỨNG THÌ PHẢI BÁO REJECTED NGAY):\n"
                "1. Bài đọc có viết theo phong cách Storytelling in Tech không? (Bắt đầu bằng một tình huống thực tế lỗi/nghẽn/treo ở phần 1 Đặt vấn đề, phân tích nguyên nhân ở phần 2, đưa ra giải pháp mới ở phần 3, minh họa code ở phần 4, áp dụng giải pháp để sửa lỗi phần 1 ở phần 5).\n"
                "2. Bộ câu hỏi kiểm tra ở phần 7 có đúng 3 câu hỏi tự luận ngắn tương ứng với 3 mức độ: Câu 1 (Thông hiểu về bản chất/tại sao dùng), Câu 2 (Vận dụng dự đoán kết quả code), Câu 3 (Phân tích xử lý tình huống lỗi) không?\n"
                "3. Có chứa bất kỳ biểu tượng cảm xúc (emoji/icon) nào trong tiêu đề hoặc nội dung phản hồi không? Tuyệt đối cấm sử dụng emoji.\n\n"
                "BẮT BUỘC TRẢ VỀ JSON CÓ CẤU TRÚC CHÍNH XÁC NHƯ SAU:\n"
                "{\n"
                '  "status": "APPROVED" hoặc "REJECTED",\n'
                '  "reason": "Giải thích chi tiết lý do duyệt hoặc lý do từ chối cụ thể kèm hướng dẫn từng bước cách sửa đổi bài đọc cho đúng tiêu chuẩn"\n'
                "}"
            )
            
            eval_prompt = f"Hãy đánh giá bài đọc sau:\n{json.dumps(reading_json, ensure_ascii=False, indent=2)}"
            
            print("   [Reflection Loop] Dang goi Truong bo mon LLM de kiem dinh chat luong...")
            eval_res = ollama.chat(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": evaluation_instruction},
                    {"role": "user", "content": eval_prompt}
                ],
                format="json"
            )
            
            eval_data = json.loads(eval_res['message']['content'])
            status = eval_data.get("status", "REJECTED").upper()
            reason = eval_data.get("reason", "Không có mô tả chi tiết lý do.")
            
            if status == "REJECTED":
                print(f"   [Reflection Loop] Kiem duyet THAT BAI: {reason}")
                return f"Lỗi kiểm duyệt chất lượng (REJECTED): {reason}. Vui lòng tự sửa đổi bài đọc cho đúng quy chuẩn và gọi lại công cụ này."
                
            print("   [Reflection Loop] Kiem duyet THANH CONG: APPROVED.")
            
            # --- LƯU TRỮ VẬT LÝ SAU KHI ĐƯỢC PHÊ DUYỆT ---
            safe_name = chu_de.replace(" ", "_").replace("-", "_")
            json_file_path = os.path.join(config.OUTPUT_JSON_DIR, f"RawAgent_Reading_{safe_name}.json")
            with open(json_file_path, "w", encoding="utf-8") as f:
                json.dump(reading_json, f, ensure_ascii=False, indent=4)
                
            # Đóng gói sang Markdown
            md_file_path = publish_reading_to_markdown(reading_json)
            if md_file_path:
                return f"Kiểm duyệt thông qua (APPROVED). Đã xuất bản file JSON tại '{json_file_path}' và file Markdown tại '{md_file_path}'."
            return "Kiểm duyệt thông qua nhưng gặp lỗi khi xuất bản file Markdown."
            
        except Exception as e:
            return f"Lỗi trong quá trình kiểm duyệt và xuất bản bài đọc: {str(e)}"

    def _tool_publish_homework_markdown(self, homework_json):
        try:
            chu_de = homework_json.get("chu_de", "Bai_Tap")
            subject = homework_json.get("subject", "python").lower()
            print(f"   [Publisher Tool] Tiến hành gửi bài tập học phần '{chu_de}' qua vòng lặp kiểm duyệt (Reflection Loop) môn '{subject}'...")
            
            # --- 1. KIỂM DUYỆT CỨNG BẰNG PYTHON (PROGRAMMATIC VALIDATION) ---
            validation_error = self._validate_homework_structure(homework_json)
            if validation_error:
                print(f"   [Programmatic Validation] Kiem duyet THAT BAI: {validation_error}")
                return f"Lỗi kiểm duyệt chất lượng (REJECTED): {validation_error} Vui lòng tự sửa đổi bài tập cho đúng quy chuẩn và gọi lại công cụ này."
            
            print("   [Programmatic Validation] Kiem duyet cau truc thanh cong.")
            
            # --- 2. ĐỌC QUY CHUẨN ĐỂ LLM SUPERVISOR KIỂM DUYỆT SÂU ---
            standards_context = ""
            try:
                standards_dir = os.path.join(config.DIR_STANDARDS, subject.capitalize())
                if os.path.exists(standards_dir):
                    contents = []
                    for f_name in os.listdir(standards_dir):
                        if f_name.endswith(('.txt', '.md')):
                            with open(os.path.join(standards_dir, f_name), "r", encoding="utf-8") as sf:
                                contents.append(sf.read())
                    if contents:
                        standards_context = "\n\n".join(contents)
                        print(f"   [Publisher Tool] Da doc truc tiep quy chuan tu o cung ({len(standards_context)} ky tu).")
            except Exception as fe:
                print(f"   [Publisher Tool] Loi doc quy chuan truc tiep: {fe}")

            if not standards_context:
                try:
                    res = self.chroma_client.col_standards.query(
                        query_texts=["Quy định xây dựng hệ thống bài tập"],
                        n_results=10,
                        where={"subject": subject}
                    )
                    if res and res.get('documents') and len(res['documents']) > 0:
                        standards_context = "\n\n".join(res['documents'][0])
                        print(f"   [Publisher Tool] Da tai quy chuan du phong tu Vector DB ({len(standards_context)} ky tu).")
                except Exception as dbe:
                    print(f"   [ChromaDB Warning] Loi khi truy van quy chuan du phong: {dbe}")
            
            if not standards_context:
                standards_context = (
                    "Quy chuẩn bắt buộc:\n"
                    "1. Gồm 5 bài (Bài 1&2: 1.5đ, Bài 3: 2đ, Bài 4: 2đ, Bài 5: 3đ), tổng điểm bằng 10.\n"
                    "2. Cấm ghi hướng dẫn giải thuật (HOW) trong đề bài.\n"
                    "3. Có bối cảnh thực tế đồng nhất, có bẫy dữ liệu."
                )

            # --- VÒNG LẶP KIỂM DUYỆT CHẤT LƯỢNG (REFLECTION LOOP) ---
            evaluation_instruction = (
                "Bạn là một Trưởng bộ môn kiểm định chất lượng học liệu chuyên nghiệp.\n"
                "Nhiệm vụ của bạn là đánh giá chất lượng bộ bài tập về nhà do AI Agent thiết kế sau đây.\n\n"
                "Bạn BẮT BUỘC phải đối chiếu kỹ lượng bộ bài tập với Tài liệu Quy chuẩn học liệu được cung cấp dưới đây.\n\n"
                f"--- TÀI LIỆU QUY CHUẨN KIỂM ĐỊNH ---\n{standards_context}\n--------------------------------------\n\n"
                "Các điểm kiểm tra cốt lõi bắt buộc (NẾU BÀI TẬP KHÔNG ĐÁP ỨNG THÌ PHẢI BÁO REJECTED NGAY):\n"
                "1. Số lượng bài tập có đúng là 5 bài theo đúng phân cấp (2 Vận dụng cơ bản, 1 Vận dụng chuyên sâu, 1 Phân tích, 1 Sáng tạo) không?\n"
                "2. Các bài Vận dụng cơ bản (Bài 1 & 2) có chứa mã nguồn lỗi trong trường 'code_loi_chua_sua' và yêu cầu học viên chỉ ra lỗi logic/vá lỗi không? (Cấm việc bắt học viên viết code từ đầu cho bài cơ bản).\n"
                "3. CẤM CHỈ ĐỊNH GIẢI THUẬT (ĐÓNG HOW): Đề bài tuyệt đối không được viết các câu hướng dẫn thuật toán hay hàm cụ thể kiểu 'sử dụng vòng lặp for', 'dùng hàm append', 'dùng split', v.v. Sinh viên phải tự quyết định cách giải. Nếu đề bài CHỈ mô tả nghiệp vụ (What) và lý do (Why) mà KHÔNG hướng dẫn thuật toán, đây là hành vi ĐÚNG ĐẮN, bạn phải phê duyệt. Nghiêm cấm từ chối bài tập vì lý do 'thiếu hướng dẫn thuật toán/hàm số'.\n"
                "4. Bài tập có bối cảnh dự án/vai diễn (Roleplay) thực tế không hay là các bài toán học vô tri (UCLN, in mảng, in số tự nhiên...)?\n"
                "5. Có cài cắm bẫy dữ liệu dị biệt (Edge cases) và yêu cầu sinh viên viết code chặn lỗi để tránh crash không?\n"
                "6. Tổng số điểm của cả bộ bài tập có đúng bằng 10 điểm hay không? (Bắt buộc phân bổ: Bài 1: 1.5đ, Bài 2: 1.5đ, Bài 3: 2đ, Bài 4: 2đ, Bài 5: 3đ).\n"
                "7. Các bài tập có chung một bối cảnh nghiệp vụ đồng nhất (E-commerce, FinTech...) và bài sau kế thừa bài trước không?\n"
                "8. Các phần 'yeu_cau_chi_tiet' có chứa đúng các đầu mục con quy định cho từng cấp độ bài tập không?\n\n"
                "BẮT BUỘC TRẢ VỀ JSON CÓ CẤU TRÚC CHÍNH XÁC NHƯ SAU:\n"
                "{\n"
                '  "status": "APPROVED" hoặc "REJECTED",\n'
                '  "reason": "Giải thích chi tiết lý do duyệt hoặc lý do từ chối cụ thể kèm hướng dẫn từng bước cách sửa đổi bài tập cho đúng tiêu chuẩn"\n'
                "}"
            )
            
            eval_prompt = f"Hãy đánh giá bộ bài tập sau:\n{json.dumps(homework_json, ensure_ascii=False, indent=2)}"
            
            print("   [Reflection Loop] Dang goi Truong bo mon LLM de kiem dinh chat luong...")
            eval_res = ollama.chat(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": evaluation_instruction},
                    {"role": "user", "content": eval_prompt}
                ],
                format="json"
            )
            
            eval_data = json.loads(eval_res['message']['content'])
            status = eval_data.get("status", "REJECTED").upper()
            reason = eval_data.get("reason", "Không có mô tả chi tiết lý do.")
            
            if status == "REJECTED":
                print(f"   [Reflection Loop] Kiem duyet THAT BAI: {reason}")
                return f"Lỗi kiểm duyệt chất lượng (REJECTED): {reason}. Vui lòng tự sửa đổi bài tập cho đúng quy chuẩn và gọi lại công cụ này."
                
            print("   [Reflection Loop] Kiem duyet THANH CONG: APPROVED.")
            
            # --- LƯU TRỮ VẬT LÝ SAU KHI ĐƯỢC PHÊ DUYỆT ---
            safe_name = chu_de.replace(" ", "_").replace("-", "_")
            json_file_path = os.path.join(config.OUTPUT_JSON_DIR, f"RawAgent_{safe_name}.json")
            with open(json_file_path, "w", encoding="utf-8") as f:
                json.dump(homework_json, f, ensure_ascii=False, indent=4)
                
            # Đóng gói sang Markdown
            md_file_path = publish_json_to_markdown(homework_json)
            if md_file_path:
                return f"Kiểm duyệt thông qua (APPROVED). Đã xuất bản file JSON tại '{json_file_path}' và file Markdown tại '{md_file_path}'."
            return "Kiểm duyệt thông qua nhưng gặp lỗi khi xuất bản file Markdown."
            
        except Exception as e:
            return f"Lỗi trong quá trình kiểm duyệt và xuất bản: {str(e)}"

    def _tool_fetch_rikkei_systems(self):
        print("   [Rikkei API Tool] Goi API de lay danh sach He dao tao...")
        systems = self.api_service.get_systems()
        if systems:
            return json.dumps(systems, ensure_ascii=False, indent=2)
        return "Thất bại: Token hết hạn hoặc server bảo trì."

    def _tool_sync_homework_to_rikkei(self, homework_json):
        print("   [Rikkei API Tool] Dang dong bo hoa bai tap len Rikkei Portal...")
        success = self.api_service.post_homework(homework_json)
        if success:
            return "Đồng bộ bài tập lên Rikkei Portal thành công!"
        return "Thất bại khi kết nối máy chủ đồng bộ."

    # --- HÀM CHẠY CHÍNH ---

    def run_agent(self, user_command):
        """
        Kích hoạt vòng lặp tư duy tự quyết định công cụ (ReAct loop) của RikkeiAgent.
        """
        print(f"\n[Agent] Da tiep nhan yeu cau hanh dong tu tri: '{user_command}'")
        
        is_reading = "bài đọc" in user_command.lower() or "reading" in user_command.lower()
        if is_reading:
            strict_instruction = (
                self.system_instruction + 
                "\n\nLƯU Ý ĐẶC BIỆT: Yêu cầu hiện tại của người dùng là thiết kế BÀI ĐỌC (Reading). Bạn BẮT BUỘC phải gọi công cụ 'publish_reading_markdown' và cấm tuyệt đối gọi 'publish_homework_markdown'. Đảm bảo cấu trúc JSON bài đọc có đủ các khoá tieu_de và noi_dung cho từng phần I-VI như đã được định nghĩa."
            )
        else:
            strict_instruction = (
                self.system_instruction + 
                "\n\nLƯU Ý ĐẶC BIỆT: Yêu cầu hiện tại của người dùng là thiết kế BÀI TẬP VỀ NHÀ (Homework). Bạn BẮT BUỘC phải gọi công cụ 'publish_homework_markdown' và cấm tuyệt đối gọi 'publish_reading_markdown'."
            )
            
        final_answer = self.chat_with_tools(
            user_message=user_command,
            system_instruction=strict_instruction,
            tools_map=self.tools_map
        )
        return final_answer
