# BÀI ĐỌC CHI TIẾT: XỬ LÝ LOGIC GIẢM GIÁ VỚI IF-ELSE (JAVA)

---

## I. Rika Shopee áp dụng chương trình khuyến mãi

Shopee cần xử lý hai loại mã giảm giá:
- DEAL0D: Giảm giá 100% cho đơn hàng >= 200k
- SALE100K: Giảm 100.000đ cho đơn hàng >= 200k.
Hãy giúp Rika viết chương trình Java để xử lý logic giảm giá này!

---

## II. Phân tích nhu cầu và lập luận giải pháp

Rika cần sử dụng câu lệnh if-else để kiểm tra điều kiện đơn hàng và mã giảm giá. Câu lệnh sẽ tính toán tổng tiền phải trả sau khi áp dụng khuyến mãi.

---

## III. Giới thiệu cú pháp và logic if-else

Cú pháp if-else trong Java:
if (điều kiện) {
  // Code thực hiện nếu điều kiện đúng
} else {
 // Code thực hiện nếu điều kiện sai
}

---

## IV. Ví dụ minh họa chương trình xử lý giảm giá

```java
public class DiscountCalculation {
    public static void main(String[] args) {
        double orderValue = 250000;
        String voucher = "SALE100K";

        if (orderValue >= 200000 && voucher.equals("SALE100K")) {
            double payment = orderValue - 100000;
            System.out.println("Bạn được giảm 100.000đ. Số tiền cần trả: " + payment);
        } else if (orderValue >= 200000 && voucher.equals("DEAL0D")) {
            double payment = 0;
            System.out.println("Chúc mừng! Bạn được giảm giá 0đ thanh toán.");
        } 
    }
}
```

---

## V. Áp dụng chương trình vào trường hợp thực tế

Bạn có thể thay đổi giá trị `orderValue` và `voucher` để kiểm tra kết quả tính toán.

---

## VI. Tổng kết kiến thức và lưu ý

Câu lệnh if-else là công cụ hữu hiệu cho việc xử lý logic phức tạp. Hãy chú ý đến thứ tự thực thi các điều kiện và cách sử dụng phương thức `equals()` để so sánh chuỗi.

---

## VII. Câu hỏi kiểm tra độ hiểu của bài đọc

* **Câu 1 (Thông hiểu):** Giải thích tại sao Rika cần sử dụng câu lệnh if-else trong chương trình của mình.
* **Câu 2 (Vận dụng):** Tìm lỗi trong đoạn code sau và đề xuất cách sửa chữa.
```java
if (orderValue >= 200000) {
            payment = orderValue - 100000;
            System.out.println("Bạn được giảm 100.000đ. Số tiền cần trả: " + payment);
} else {
            // Code xử lý trường hợp không áp dụng khuyến mãi
}
```
* **Câu 3 (Phân tích):** Xét tình huống `orderValue` là 150000 và `voucher` là "SALE100K". Hãy phân tích logic chương trình và cho biết giá trị `payment` sẽ bằng bao nhiêu?

