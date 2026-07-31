import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [payloadArg, outputArg, qaArg] = process.argv.slice(2);
if (!payloadArg || !outputArg || !qaArg) {
  throw new Error("Usage: build_excel.mjs payload.json output.xlsx qa_dir");
}

const payload = JSON.parse(await fs.readFile(payloadArg, "utf8"));
const outputPath = path.resolve(outputArg);
const qaDir = path.resolve(qaArg);
await fs.mkdir(path.dirname(outputPath), { recursive: true });
await fs.mkdir(qaDir, { recursive: true });

const workbook = Workbook.create();
const allSheet = workbook.worksheets.add("All Articles");
const packagingSheet = workbook.worksheets.add("Packaging Relevant");
const companiesSheet = workbook.worksheets.add("Companies");
const sourcesSheet = workbook.worksheets.add("Sources");

const palette = {
  navy: "#163B5C",
  teal: "#0F766E",
  lightTeal: "#DFF3EF",
  blue: "#DCEAF7",
  amber: "#FFF2CC",
  red: "#FCE8E6",
  gray: "#E5E7EB",
  white: "#FFFFFF",
  text: "#1F2937",
};

function isoDate(value) {
  return value ? new Date(`${value}T00:00:00Z`) : null;
}

function addDataSheet(sheet, headers, rows, tableName, widths, dateColumns = []) {
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);
  const matrix = [headers, ...rows];
  sheet.getRangeByIndexes(0, 0, matrix.length, headers.length).values = matrix;
  const endRow = Math.max(2, matrix.length);
  const endColumnLetter = columnLetter(headers.length);
  const table = sheet.tables.add(`A1:${endColumnLetter}${endRow}`, true, tableName);
  table.style = "TableStyleMedium2";
  table.showFilterButton = true;
  sheet.getRange(`A1:${endColumnLetter}1`).format = {
    fill: palette.navy,
    font: { bold: true, color: palette.white },
    rowHeight: 52,
    verticalAlignment: "center",
    wrapText: true,
  };
  if (matrix.length > 1) {
    sheet.getRange(`A2:${endColumnLetter}${matrix.length}`).format = {
      verticalAlignment: "top",
      wrapText: true,
      font: { color: palette.text },
    };
  }
  widths.forEach((width, index) => {
    sheet.getRangeByIndexes(0, index, endRow, 1).format.columnWidth = width;
  });
  dateColumns.forEach((index) => {
    if (matrix.length > 1) {
      sheet.getRangeByIndexes(1, index, matrix.length - 1, 1).format.numberFormat = "yyyy-mm-dd";
    }
  });
  return { endRow: matrix.length, endColumnLetter };
}

function columnLetter(count) {
  let value = count;
  let result = "";
  while (value > 0) {
    value -= 1;
    result = String.fromCharCode(65 + (value % 26)) + result;
    value = Math.floor(value / 26);
  }
  return result;
}

const allHeaders = [
  "month", "country", "title", "source", "published_date", "business_categories",
  "device_relevance_score", "packaging_relevance_score", "priority_level",
  "matched_keywords", "summary_placeholder", "url",
];
const allRows = payload.all_articles.map((row) => [
  row.month, row.country, row.title, row.source, isoDate(row.published_date),
  row.business_categories, row.device_relevance_score, row.packaging_relevance_score,
  row.priority_level, row.matched_keywords, row.summary_placeholder, row.url,
]);
const allInfo = addDataSheet(
  allSheet,
  allHeaders,
  allRows,
  "AllArticlesTable",
  [12, 10, 42, 26, 14, 28, 16, 18, 14, 32, 58, 52],
  [4],
);
if (allRows.length) {
  allSheet.getRange(`G2:H${allInfo.endRow}`).format.numberFormat = "0";
  allSheet.getRange(`G2:G${allInfo.endRow}`).conditionalFormats.add("colorScale", {
    colors: ["#FCE8E6", "#FFF2CC", "#DFF3EF"],
    thresholds: ["min", "50%", "max"],
  });
  allSheet.getRange(`H2:H${allInfo.endRow}`).conditionalFormats.add("dataBar", {
    color: palette.teal,
    gradient: true,
  });
}

const packagingHeaders = [
  ...allHeaders,
  "packaging_material", "packaging_format", "sterilization_method",
  "sterile_barrier_relevance", "ISO_11607_relevance", "possible_business_implication",
];
const packagingRows = payload.packaging_articles.map((row) => [
  row.month, row.country, row.title, row.source, isoDate(row.published_date),
  row.business_categories, row.device_relevance_score, row.packaging_relevance_score,
  row.priority_level, row.matched_keywords, row.summary_placeholder, row.url,
  row.packaging_material, row.packaging_format, row.sterilization_method,
  row.sterile_barrier_relevance, row.ISO_11607_relevance, row.possible_business_implication,
]);
const packagingInfo = addDataSheet(
  packagingSheet,
  packagingHeaders,
  packagingRows,
  "PackagingRelevantTable",
  [12, 10, 40, 24, 14, 26, 16, 18, 14, 30, 50, 48, 24, 24, 24, 34, 25, 48],
  [4],
);
packagingSheet.freezePanes.freezeColumns(2);
if (packagingRows.length) {
  packagingSheet.getRange(`H2:H${packagingInfo.endRow}`).format.numberFormat = "0";
  packagingSheet.getRange(`H2:H${packagingInfo.endRow}`).conditionalFormats.add("cellIs", {
    operator: "greaterThanOrEqual",
    formula: payload.packaging_threshold,
    format: { fill: palette.lightTeal, font: { bold: true, color: palette.teal } },
  });
}

const companyHeaders = [
  "company_name", "country", "event_type", "number_of_mentions", "related_articles",
  "packaging_relevance", "latest_update_date",
];
const companyRows = payload.companies.map((row) => [
  row.company_name, row.country, row.event_type, row.number_of_mentions,
  row.related_articles, row.packaging_relevance, isoDate(row.latest_update_date),
]);
const companyInfo = addDataSheet(
  companiesSheet,
  companyHeaders,
  companyRows,
  "CompaniesTable",
  [34, 10, 30, 18, 60, 20, 18],
  [6],
);
if (companyRows.length) {
  companiesSheet.getRange(`D2:F${companyInfo.endRow}`).format.numberFormat = "0";
}

const sourceHeaders = [
  "source_name", "country", "organization", "number_of_articles", "successful_scrapes",
  "failed_scrapes", "latest_article_date",
];
const sourceRows = payload.sources.map((row) => [
  row.source_name, row.country, row.organization, row.number_of_articles,
  row.successful_scrapes, row.failed_scrapes, isoDate(row.latest_article_date),
]);
const sourceInfo = addDataSheet(
  sourcesSheet,
  sourceHeaders,
  sourceRows,
  "SourcesTable",
  [32, 10, 40, 18, 18, 16, 18],
  [6],
);
if (sourceRows.length) {
  sourcesSheet.getRange(`D2:F${sourceInfo.endRow}`).format.numberFormat = "0";
  sourcesSheet.getRange(`F2:F${sourceInfo.endRow}`).conditionalFormats.add("cellIs", {
    operator: "greaterThan",
    formula: 0,
    format: { fill: palette.red, font: { bold: true, color: "#9C2B25" } },
  });
}

const inspections = [];
for (const [sheetName, info] of [
  ["All Articles", allInfo],
  ["Packaging Relevant", packagingInfo],
  ["Companies", companyInfo],
  ["Sources", sourceInfo],
]) {
  const inspection = await workbook.inspect({
    kind: "table",
    range: `${sheetName}!A1:${info.endColumnLetter}${Math.max(2, info.endRow)}`,
    include: "values,formulas",
    tableMaxRows: 8,
    tableMaxCols: 18,
    maxChars: 5000,
  });
  inspections.push(inspection.ndjson);
  const preview = await workbook.render({
    sheetName,
    autoCrop: "all",
    scale: 1,
    format: "png",
  });
  await fs.writeFile(
    path.join(qaDir, `${sheetName.toLowerCase().replaceAll(" ", "_")}.png`),
    new Uint8Array(await preview.arrayBuffer()),
  );
}

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
});
await fs.writeFile(
  path.join(qaDir, "inspection.txt"),
  `${inspections.join("\n")}\nFORMULA_ERRORS\n${errors.ndjson}\n`,
  "utf8",
);

const exported = await SpreadsheetFile.exportXlsx(workbook);
await exported.save(outputPath);
console.log(JSON.stringify({
  outputPath,
  sheets: ["All Articles", "Packaging Relevant", "Companies", "Sources"],
  rows: {
    allArticles: allRows.length,
    packagingRelevant: packagingRows.length,
    companies: companyRows.length,
    sources: sourceRows.length,
  },
}));
