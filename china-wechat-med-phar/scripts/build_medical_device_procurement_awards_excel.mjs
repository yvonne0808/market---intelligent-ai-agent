import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";


const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const projectDir = path.resolve(scriptDir, "..");
const inputPath = path.resolve(
  process.argv[2] ||
    path.join(
      projectDir,
      "data/extracted/Medical Device/procurement_awards_2026_06_2026_07.json",
    ),
);
const outputPath = path.resolve(
  process.argv[3] ||
    path.join(
      projectDir,
      "outputs/Medical Device/medical_device_procurement_awards_2026_06_2026_07.xlsx",
    ),
);

const articles = JSON.parse(await fs.readFile(inputPath, "utf8"));
if (!Array.isArray(articles)) {
  throw new Error(`Input must contain a JSON list: ${inputPath}`);
}

const validArticles = articles.filter(
  (article) => article?.is_valid_award_notice === true && Array.isArray(article.awards),
);
const awardRows = [];
for (const article of validArticles) {
  for (const award of article.awards) {
    if (!award?.company_name) continue;
    awardRows.push([
      awardRows.length + 1,
      article._filter_source_period || "",
      article.announcement_date || "",
      article.published ? article.published.slice(0, 10) : "",
      article.notice_scope || "",
      article.procurement_level || "",
      article.procurement_project_name || "",
      award.category_product || "",
      award.product_name || "",
      award.specification_model || "",
      award.company_name || "",
      award.applicant_company || "",
      award.registrant_name || "",
      award.manufacturer_name || "",
      award.registration_certificate_no || "",
      award.bidding_unit || "",
      award.procurement_group || "",
      award.region || "",
      award.award_status || "",
      award.award_price ?? null,
      award.currency || "",
      award.price_unit || "",
      award.award_price_text || "",
      award.procurement_volume ?? null,
      award.volume_unit || "",
      award.procurement_volume_text || "",
      award.price_reduction ?? null,
      award.price_reduction_text || "",
      award.contract_amount ?? null,
      award.contract_amount_currency || "",
      award.contract_amount_text || "",
      award.execution_period || "",
      award.evidence_text || "",
      article.source_confidence || "",
      article.title || "",
      article.source_name || "",
      article.link || "",
      article.article_id || "",
    ]);
  }
}

const reviewRows = articles.map((article, index) => [
  index + 1,
  article._filter_source_period || "",
  article.published ? article.published.slice(0, 10) : "",
  article.title || "",
  article.source_name || "",
  article.is_valid_award_notice === true ? "有效" : "无效",
  Array.isArray(article.awards) ? article.awards.length : 0,
  article.procurement_project_name || "",
  Array.isArray(article.regions) ? article.regions.join("、") : "",
  article.invalid_reason || "",
  article.summary_cn || "",
  article.source_confidence || "",
  article.link || "",
  article.article_id || "",
]);

const workbook = Workbook.create();
const summary = workbook.worksheets.add("汇总");
const awards = workbook.worksheets.add("中标明细");
const review = workbook.worksheets.add("文章审核");

const awardHeaders = [
  "序号", "来源月份", "结果公告日期", "文章日期", "集采范围", "采购层级", "项目名称",
  "类别-品种", "产品名称", "规格型号", "中选企业", "申报企业", "医疗器械注册人",
  "生产企业", "注册证号", "竞价单元", "采购组", "地区", "中选状态", "中选价格",
  "币种", "价格单位", "价格原文", "采购量", "数量单位", "采购量原文", "降价幅度",
  "降幅原文", "合同金额", "合同币种", "合同金额原文", "执行周期", "关键证据",
  "来源可信度", "文章标题", "文章来源", "原文链接", "Article ID",
];
const reviewHeaders = [
  "序号", "来源月份", "文章日期", "文章标题", "文章来源", "判断结果", "中标记录数",
  "项目名称", "涉及地区", "无效原因", "文章摘要", "来源可信度", "原文链接", "Article ID",
];

awards.getRangeByIndexes(0, 0, 1, awardHeaders.length).values = [awardHeaders];
if (awardRows.length) {
  awards.getRangeByIndexes(1, 0, awardRows.length, awardHeaders.length).values = awardRows;
}
review.getRangeByIndexes(0, 0, 1, reviewHeaders.length).values = [reviewHeaders];
if (reviewRows.length) {
  review.getRangeByIndexes(1, 0, reviewRows.length, reviewHeaders.length).values = reviewRows;
}

const awardEndRow = Math.max(2, awardRows.length + 1);
const reviewEndRow = Math.max(2, reviewRows.length + 1);
awards.tables.add(`A1:AL${awardEndRow}`, true, "ProcurementAwardsTable");
review.tables.add(`A1:N${reviewEndRow}`, true, "ArticleReviewTable");
awards.tables.getItem("ProcurementAwardsTable").style = "TableStyleMedium2";
review.tables.getItem("ArticleReviewTable").style = "TableStyleMedium4";

for (const sheet of [awards, review]) {
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);
  sheet.getRange("1:1").format = {
    fill: "#145B63",
    font: { bold: true, color: "#FFFFFF" },
    rowHeight: 30,
    verticalAlignment: "center",
    wrapText: true,
  };
}

awards.freezePanes?.freezeColumns?.(4);
awards.getRange(`A2:A${awardEndRow}`).format.numberFormat = "0";
awards.getRange(`T2:T${awardEndRow}`).format.numberFormat = "#,##0.00";
awards.getRange(`X2:X${awardEndRow}`).format.numberFormat = "#,##0.00";
awards.getRange(`AA2:AA${awardEndRow}`).format.numberFormat = "0.0%";
awards.getRange(`AC2:AC${awardEndRow}`).format.numberFormat = "#,##0.00";
awards.getRange(`A1:AL${awardEndRow}`).format.verticalAlignment = "top";
awards.getRange(`A1:AL${awardEndRow}`).format.wrapText = true;
review.getRange(`A1:N${reviewEndRow}`).format.verticalAlignment = "top";
review.getRange(`A1:N${reviewEndRow}`).format.wrapText = true;

const widths = {
  A: 8, B: 12, C: 14, D: 12, E: 14, F: 12, G: 30, H: 28, I: 22, J: 20,
  K: 26, L: 26, M: 26, N: 26, O: 20, P: 14, Q: 14, R: 14, S: 12, T: 14,
  U: 10, V: 12, W: 20, X: 14, Y: 12, Z: 20, AA: 12, AB: 18, AC: 14, AD: 12,
  AE: 20, AF: 16, AG: 40, AH: 12, AI: 42, AJ: 18, AK: 45, AL: 32,
};
for (const [column, width] of Object.entries(widths)) {
  awards.getRange(`${column}:${column}`).format.columnWidth = width;
}
const reviewWidths = [8, 12, 12, 42, 18, 12, 12, 30, 18, 34, 40, 12, 45, 32];
reviewWidths.forEach((width, index) => {
  review.getRangeByIndexes(0, index, reviewEndRow, 1).format.columnWidth = width;
});

review.getRange(`F2:F${reviewEndRow}`).conditionalFormats.add("containsText", {
  text: "有效",
  format: { fill: "#DFF3E4", font: { color: "#176B3A", bold: true } },
});
review.getRange(`F2:F${reviewEndRow}`).conditionalFormats.add("containsText", {
  text: "无效",
  format: { fill: "#F5E7E7", font: { color: "#8A3030" } },
});

summary.showGridLines = false;
summary.getRange("A1:H2").merge();
summary.getRange("A1").values = [["医疗器械集采中标信息汇总"]];
summary.getRange("A1:H2").format = {
  fill: "#0E4A52",
  font: { bold: true, color: "#FFFFFF", size: 20 },
  verticalAlignment: "center",
  horizontalAlignment: "left",
};
summary.getRange("A4:B7").values = [
  ["指标", "数量"],
  ["审核文章数", null],
  ["有效中标文章数", null],
  ["中标明细记录数", null],
];
summary.getRange("B5").formulas = [[`=COUNTA('文章审核'!$A$2:$A$${reviewEndRow})`]];
summary.getRange("B6").formulas = [[`=COUNTIF('文章审核'!$F$2:$F$${reviewEndRow},"有效")`]];
summary.getRange("B7").formulas = [[`=COUNTA('中标明细'!$A$2:$A$${awardEndRow})`]];
summary.getRange("A4:B4").format = {
  fill: "#DDEFF1",
  font: { bold: true, color: "#173E43" },
};
summary.getRange("A4:B7").format.borders = {
  preset: "all",
  style: "thin",
  color: "#C7D9DC",
};
summary.getRange("A9:H13").merge();
summary.getRange("A9").values = [[
  "使用说明：\n1. “文章审核”保留全部候选文章及有效/无效判断。\n2. “中标明细”仅保留有效记录，每行对应企业＋产品＋规格＋地区＋状态的唯一组合。\n3. 空白字段表示原文未披露，不应自行推断。\n4. 所有记录均保留原文链接和关键证据，建议用于内部筛选后再对外使用。",
]];
summary.getRange("A9:H13").format = {
  fill: "#F2F7F8",
  font: { color: "#425B60", size: 11 },
  wrapText: true,
  verticalAlignment: "top",
};
summary.getRange("A:A").format.columnWidth = 24;
summary.getRange("B:B").format.columnWidth = 16;

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(outputPath);
