"""基于 OCR 位置信息的结构识别."""

from dataclasses import dataclass
from typing import Literal


@dataclass
class OCRBox:
    """OCR 识别的文本框."""

    text: str
    bbox: list[list[float]]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
    confidence: float

    @property
    def x_min(self) -> float:
        return min(p[0] for p in self.bbox)

    @property
    def x_max(self) -> float:
        return max(p[0] for p in self.bbox)

    @property
    def y_min(self) -> float:
        return min(p[1] for p in self.bbox)

    @property
    def y_max(self) -> float:
        return max(p[1] for p in self.bbox)

    @property
    def width(self) -> float:
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        return self.y_max - self.y_min

    @property
    def center_x(self) -> float:
        return (self.x_min + self.x_max) / 2

    @property
    def center_y(self) -> float:
        return (self.y_min + self.y_max) / 2


@dataclass
class StructuredOCRBlock:
    """基于位置的结构化文本块."""

    type: Literal["title", "heading", "paragraph", "list_item", "table_cell"]
    text: str
    level: int = 0
    confidence: float = 1.0
    bbox: list[list[float]] | None = None


class LayoutBasedStructurer:
    """基于布局的 OCR 结构识别."""

    def __init__(self, image_width: int, image_height: int):
        self.image_width = image_width
        self.image_height = image_height

    def structure_ocr_boxes(self, boxes: list[OCRBox]) -> list[StructuredOCRBlock]:
        """基于位置信息识别结构."""
        if not boxes:
            return []

        # 按 Y 坐标排序（从上到下）
        sorted_boxes = sorted(boxes, key=lambda b: b.y_min)

        # 计算字体大小分布
        font_sizes = [box.height for box in sorted_boxes]
        avg_font_size = sum(font_sizes) / len(font_sizes)
        max_font_size = max(font_sizes)

        blocks = []

        for i, box in enumerate(sorted_boxes):
            block_type = self._detect_block_type(box, sorted_boxes, i, avg_font_size, max_font_size)

            level = self._calculate_level(box, avg_font_size, max_font_size)

            blocks.append(
                StructuredOCRBlock(
                    type=block_type, text=box.text, level=level, confidence=box.confidence, bbox=box.bbox
                )
            )

        return blocks

    def _detect_block_type(
        self, box: OCRBox, all_boxes: list[OCRBox], index: int, avg_font_size: float, max_font_size: float
    ) -> str:
        """根据位置和大小判断文本类型."""

        # 1. 标题判断：字体大、居中、短文本
        if self._is_title(box, avg_font_size, max_font_size):
            return "title"

        # 2. 列表判断：左侧缩进、有项目符号
        if self._is_list_item(box, all_boxes, index):
            return "list_item"

        # 3. 表格判断：对齐、等宽
        if self._is_table_cell(box, all_boxes, index):
            return "table_cell"

        # 4. 小标题判断：字体稍大、左对齐
        if box.height > avg_font_size * 1.2:
            return "heading"

        # 5. 默认：段落
        return "paragraph"

    def _is_title(self, box: OCRBox, avg_font_size: float, max_font_size: float) -> bool:
        """判断是否为标题."""
        # 字体大（> 平均 1.5 倍）
        if box.height < avg_font_size * 1.5:
            return False

        # 文本短（< 30 字符）
        if len(box.text) > 30:
            return False

        # 居中（中心点在图片中间 40%-60% 区域）
        center_ratio = box.center_x / self.image_width
        if 0.3 < center_ratio < 0.7:
            return True

        # 或者是最大字体
        if box.height >= max_font_size * 0.9:
            return True

        return False

    def _is_list_item(self, box: OCRBox, all_boxes: list[OCRBox], index: int) -> bool:
        """判断是否为列表项."""
        # 检查是否有项目符号
        if box.text.strip().startswith(("•", "·", "○", "■", "□")):
            return True

        # 检查是否有数字前缀
        import re

        if re.match(r"^\d+[.、)]", box.text.strip()):
            return True

        # 检查左侧缩进
        if index > 0:
            prev_box = all_boxes[index - 1]
            # 如果比前一行缩进
            if box.x_min > prev_box.x_min + 20:
                return True

        return False

    def _is_table_cell(self, box: OCRBox, all_boxes: list[OCRBox], index: int) -> bool:
        """判断是否为表格单元格."""
        # 检查同一行是否有多个文本框（表格列）
        same_row_boxes = [
            b
            for b in all_boxes
            if abs(b.y_min - box.y_min) < 10  # Y 坐标接近
            and b != box
        ]

        # 如果同一行有 2+ 个文本框，可能是表格
        if len(same_row_boxes) >= 2:
            # 检查是否等宽或对齐
            widths = [b.width for b in same_row_boxes + [box]]
            if max(widths) / min(widths) < 2:  # 宽度相近
                return True

        return False

    def _calculate_level(self, box: OCRBox, avg_font_size: float, max_font_size: float) -> int:
        """计算层级（1-6）."""
        # 基于字体大小
        size_ratio = box.height / avg_font_size

        if size_ratio >= 2.0:
            return 1  # 主标题
        elif size_ratio >= 1.5:
            return 2  # 二级标题
        elif size_ratio >= 1.2:
            return 3  # 三级标题
        else:
            return 0  # 正文


def integrate_with_paddleocr(ocr_result, image_width: int, image_height: int) -> list[StructuredOCRBlock]:
    """集成 PaddleOCR 结果."""
    # 转换 PaddleOCR 格式
    boxes = []
    for line in ocr_result:
        bbox, (text, confidence) = line
        boxes.append(OCRBox(text=text, bbox=bbox, confidence=confidence))

    # 结构化
    structurer = LayoutBasedStructurer(image_width, image_height)
    return structurer.structure_ocr_boxes(boxes)
