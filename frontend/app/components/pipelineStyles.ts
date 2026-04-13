export const commonPipelineStyles = {
  pageContainer: "w-full max-w-7xl mx-auto p-6 space-y-6",
  pageHeader: "mb-8 flex items-center justify-between gap-4",
  pageTitle: "text-3xl font-bold text-gray-900",
  pageSubtitle: "mt-2 text-gray-600",
  redirectButtonContainer: "mt-4",
  redirectButtonPrimary:
    "inline-block rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700",
  redirectButtonSecondary:
    "inline-block rounded-md border-2 border-gray-500 bg-white px-4 py-2 text-sm font-semibold text-gray-900 hover:bg-gray-50",
  sectionStack: "space-y-6",
  blockStack: "space-y-4",
  marginBottom4: "mb-4",

  card: "bg-white rounded-lg shadow p-6",
  sectionTitle: "text-xl font-bold text-gray-900 mb-4",
  sectionTitleNoMargin: "text-xl font-bold text-gray-900",
  subSectionTitle: "text-lg font-bold text-gray-900",
  bodyText: "text-sm text-gray-700",
  mutedText: "text-xs text-gray-500",
  formLabel: "block text-sm font-semibold text-gray-900 mb-2",

  textInput:
    "w-full rounded-md border border-gray-500 bg-white px-3 py-2 text-gray-950 placeholder:text-gray-500",
  emphasizedInput:
    "w-full px-3 py-2 bg-white text-gray-950 border-2 border-gray-500 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-blue-700",

  buttonDark:
    "rounded-md bg-slate-900 px-4 py-2 font-semibold text-white hover:bg-slate-800 disabled:opacity-60",
  buttonDarkCompact:
    "rounded-md bg-slate-900 px-3 py-1.5 font-semibold text-white hover:bg-slate-800",
  buttonPrimary:
    "rounded-md bg-blue-600 px-4 py-2 font-semibold text-white hover:bg-blue-700 disabled:opacity-60",

  authSuccessBanner:
    "flex items-center justify-between rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-900",
  errorText: "text-sm text-red-700",
};

export const predictionPageStyles = {
  authGrid: "grid grid-cols-1 gap-3 md:grid-cols-3",
  trainRideInput: "md:w-72",
  modelGrid: "grid grid-cols-2 gap-3",
  modelOption: "flex cursor-pointer items-center space-x-2",
  modelCheckbox: "h-4 w-4 text-blue-600",
  modelOptionText: "text-sm text-gray-700",
  runButton:
    "w-full bg-blue-600 text-white py-3 px-4 rounded-md font-semibold hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors",
  modelLabel: "block text-sm font-medium text-gray-700 mb-3",
  errorPanel: "rounded-md border border-red-200 bg-red-50 p-4",
  errorPanelTitle: "font-medium text-red-800",
  errorPanelBody: "mt-1 text-sm text-red-700",
  summaryGrid: "grid grid-cols-3 gap-4",
  summaryCard: "rounded bg-gray-50 p-4",
  summaryLabel: "text-sm text-gray-600",
  summaryValue: "text-2xl font-bold text-gray-900",
  summaryValueMono: "text-sm font-mono font-semibold",
  tableSectionTitle: "mb-4 text-lg font-semibold text-gray-900",
  tableWrapper: "overflow-x-auto",
  table: "w-full text-sm",
  tableHeadRow: "border-b bg-gray-100",
  tableHeaderCell: "px-4 py-2 text-left font-semibold text-gray-900",
  tableRow: "border-b hover:bg-gray-50",
  tableCell: "px-4 py-2 font-mono text-xs text-gray-700",
  tableFooter: "mt-2 text-xs text-gray-500",
};

export const stravaPageStyles = {
  dashboardLink:
    "rounded-md border-2 border-gray-500 bg-white px-4 py-2 text-sm font-semibold text-gray-900 hover:bg-gray-50",
  authGrid: "mt-4 grid gap-3 md:grid-cols-3",
  authBanner: "mt-4",
  stepGrid: "grid gap-6 md:grid-cols-3",
  stepLabel: "mb-2 text-xs font-bold uppercase tracking-wide text-gray-500",
  statusPanel:
    "mt-4 rounded-md border border-gray-200 bg-gray-50 p-3 text-xs text-gray-800",
  oauthPanel:
    "mt-4 rounded-md border border-blue-200 bg-blue-50 p-3 text-xs text-blue-900",
  extractionPanel:
    "mt-4 rounded-md border border-emerald-300 bg-emerald-50 p-3 text-xs text-emerald-900",
  oauthInput:
    "w-full rounded-md border border-blue-400 bg-white px-3 py-2 text-blue-950 outline-none focus:ring-2 focus:ring-blue-500",
  actionButton:
    "rounded-md bg-blue-600 px-3 py-2 font-semibold text-white hover:bg-blue-700 disabled:opacity-60",
  openLink:
    "inline-block rounded-md bg-slate-900 px-3 py-2 font-semibold text-white hover:bg-slate-800",
  exchangeButton:
    "rounded-md bg-slate-900 px-3 py-2 font-semibold text-white hover:bg-slate-800 disabled:opacity-60",
  exchangeActions: "mt-3 flex flex-wrap gap-2",
  pasteButton:
    "rounded-md border border-slate-700 bg-white px-3 py-2 font-semibold text-slate-900 hover:bg-slate-100 disabled:opacity-60",
  exchangeSuccess:
    "mt-3 rounded-md border border-emerald-300 bg-emerald-50 p-3 text-emerald-900",
  extractionControls: "mb-3 flex items-end gap-2",
  extractionInputWrap: "flex-1",
  extractionInputLabel: "block text-xs font-semibold text-gray-700",
  extractionInput:
    "mt-1 w-full rounded-md border border-blue-400 bg-white px-3 py-2 text-gray-900 outline-none focus:ring-2 focus:ring-blue-500",
  extractionButton:
    "rounded-md bg-blue-600 px-4 py-2 font-semibold text-white hover:bg-blue-700 disabled:opacity-60",
  activationWarning: "text-amber-900",
  activityListPanel:
    "mt-3 space-y-2 rounded-md border border-emerald-200 bg-emerald-100 p-3",
  activityListTitle: "font-semibold text-emerald-900",
  activityMeta: "mt-1 space-y-1 text-gray-600",
  activityCard:
    "rounded border border-emerald-200 bg-white p-2 text-xs text-gray-700",
  inlineError: "mt-2 text-red-700",
};

export const cyclistSelectorStyles = {
  container: "space-y-2",
  label: "block text-sm font-semibold text-gray-900",
  loading: "text-sm text-gray-500",
  error: "text-sm text-red-500",
  select:
    "w-full px-3 py-2 bg-white text-gray-950 border-2 border-gray-500 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-blue-700",
  option: "bg-white text-gray-950",
  hiddenPlaceholder: "hidden",
};

export const authPageStyles = {
  wrapper: "mx-auto max-w-md",
  title: "text-3xl font-bold text-gray-900",
  subtitle: "mt-2 text-gray-600",
  errorBox:
    "mt-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700",
  form: "mt-6 space-y-4",
  submitButton: "w-full",
  switchText: "mt-6 text-sm text-gray-700",
  switchLink: "font-semibold text-blue-600 hover:underline",
};
