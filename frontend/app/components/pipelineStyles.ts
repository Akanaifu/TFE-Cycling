export const commonPipelineStyles = {
  pageContainer: "w-full max-w-7xl mx-auto p-6 space-y-6",
  pageHeader: "mb-8 flex items-center justify-between gap-4",
  pageTitle: "text-3xl font-bold text-[#ffd60a]",
  pageSubtitle: "mt-2 text-[#dbeafe]/80",
  redirectButtonContainer: "mt-4",
  redirectButtonPrimary:
    "inline-block rounded-md bg-[#ffc300] px-4 py-2 text-sm font-semibold text-[#000814] hover:bg-[#ffd60a] shadow-[0_10px_20px_rgba(255,195,0,0.18)] transition-colors",
  redirectButtonSecondary:
    "inline-block rounded-md border border-[#ffc300]/30 bg-transparent px-4 py-2 text-sm font-semibold text-[#fff8d6] hover:bg-[#003566]/60 transition-colors",
  sectionStack: "space-y-6",
  blockStack: "space-y-4",
  marginBottom4: "mb-4",

  card: "rounded-2xl border border-[#003566]/70 bg-[#001d3d]/88 p-6 shadow-[0_20px_50px_rgba(0,0,0,0.28)]",
  sectionTitle: "text-xl font-bold text-[#ffd60a] mb-4",
  sectionTitleNoMargin: "text-xl font-bold text-[#ffd60a]",
  subSectionTitle: "text-lg font-bold text-[#fff8d6]",
  bodyText: "text-sm text-[#dbeafe]/80",
  mutedText: "text-xs text-[#9fb4d2]",
  formLabel: "block text-sm font-semibold text-[#fff8d6] mb-2",

  textInput:
    "w-full rounded-md border border-[#003566] bg-[#000814]/70 px-3 py-2 text-[#fff8d6] placeholder:text-[#9fb4d2] shadow-sm focus:border-[#ffc300] focus:outline-none focus:ring-2 focus:ring-[#ffc300]/30",
  emphasizedInput:
    "w-full rounded-md border-2 border-[#003566] bg-[#000814]/75 px-3 py-2 text-[#fff8d6] shadow-sm focus:border-[#ffc300] focus:outline-none focus:ring-2 focus:ring-[#ffc300]/30",

  buttonDark:
    "rounded-md bg-[#003566] px-4 py-2 font-semibold text-[#fff8d6] hover:bg-[#00467f] disabled:opacity-60 transition-colors",
  buttonDarkCompact:
    "rounded-md bg-[#003566] px-3 py-1.5 font-semibold text-[#fff8d6] hover:bg-[#00467f] transition-colors",
  buttonPrimary:
    "rounded-md bg-[#ffc300] px-4 py-2 font-semibold text-[#000814] hover:bg-[#ffd60a] disabled:opacity-60 transition-colors",

  authSuccessBanner:
    "flex items-center justify-between rounded-md border border-[#ffc300]/20 bg-[#003566]/35 p-3 text-sm text-[#fff8d6]",
  errorText: "text-sm text-[#ffb4b4]",
};

export const predictionPageStyles = {
  authGrid: "grid grid-cols-1 gap-3 md:grid-cols-3",
  trainRideInput: "md:w-72",
  modelGrid: "grid grid-cols-2 gap-3",
  modelOption: "flex cursor-pointer items-center space-x-2",
  modelCheckbox: "h-4 w-4 text-[#ffc300]",
  modelOptionText: "text-sm text-[#dbeafe]/80",
  runButton:
    "w-full bg-[#ffc300] text-[#000814] py-3 px-4 rounded-md font-semibold hover:bg-[#ffd60a] disabled:bg-[#9fb4d2] disabled:cursor-not-allowed transition-colors",
  modelLabel: "block text-sm font-medium text-[#dbeafe]/80 mb-3",
  errorPanel: "rounded-md border border-[#ffc300]/20 bg-[#000814]/70 p-4",
  errorPanelTitle: "font-medium text-[#ffd60a]",
  errorPanelBody: "mt-1 text-sm text-[#fff8d6]",
  summaryGrid: "grid grid-cols-3 gap-4",
  summaryCard: "rounded-xl border border-[#003566] bg-[#000814]/55 p-4",
  summaryLabel: "text-sm text-[#9fb4d2]",
  summaryValue: "text-2xl font-bold text-[#fff8d6]",
  summaryValueMono: "text-sm font-mono font-semibold",
  tableSectionTitle: "mb-4 text-lg font-semibold text-[#ffd60a]",
  tableWrapper: "overflow-x-auto",
  table: "w-full text-sm",
  tableHeadRow: "border-b border-[#003566] bg-[#000814]/60",
  tableHeaderCell: "px-4 py-2 text-left font-semibold text-[#fff8d6]",
  tableRow: "border-b border-[#003566]/60 hover:bg-[#001d3d]/70",
  tableCell: "px-4 py-2 font-mono text-xs text-[#dbeafe]",
  tableFooter: "mt-2 text-xs text-[#9fb4d2]",
};

export const stravaPageStyles = {
  dashboardLink:
    "rounded-md border border-[#ffc300]/30 bg-[#000814]/70 px-4 py-2 text-sm font-semibold text-[#fff8d6] hover:bg-[#003566]/70",
  authGrid: "mt-4 grid gap-3 md:grid-cols-3",
  authBanner: "mt-4",
  stepGrid: "grid gap-6 md:grid-cols-3",
  stepLabel: "mb-2 text-xs font-bold uppercase tracking-wide text-[#9fb4d2]",
  statusPanel:
    "mt-4 rounded-md border border-[#003566] bg-[#000814]/55 p-3 text-xs text-[#dbeafe]",
  oauthPanel:
    "mt-4 rounded-md border border-[#003566] bg-[#001d3d]/70 p-3 text-xs text-[#fff8d6]",
  extractionPanel:
    "mt-4 rounded-md border border-[#ffc300]/20 bg-[#000814]/60 p-3 text-xs text-[#fff8d6]",
  oauthInput:
    "w-full rounded-md border border-[#003566] bg-[#000814]/75 px-3 py-2 text-[#fff8d6] outline-none focus:ring-2 focus:ring-[#ffc300]/30",
  actionButton:
    "rounded-md bg-[#ffc300] px-3 py-2 font-semibold text-[#000814] hover:bg-[#ffd60a] disabled:opacity-60",
  openLink:
    "inline-block rounded-md bg-[#003566] px-3 py-2 font-semibold text-[#fff8d6] hover:bg-[#00467f]",
  exchangeButton:
    "rounded-md bg-[#003566] px-3 py-2 font-semibold text-[#fff8d6] hover:bg-[#00467f] disabled:opacity-60",
  exchangeActions: "mt-3 flex flex-wrap gap-2",
  pasteButton:
    "rounded-md border border-[#ffc300]/25 bg-transparent px-3 py-2 font-semibold text-[#fff8d6] hover:bg-[#003566]/60 disabled:opacity-60",
  exchangeSuccess:
    "mt-3 rounded-md border border-[#ffc300]/20 bg-[#001d3d]/70 p-3 text-[#fff8d6]",
  extractionControls: "mb-3 flex items-end gap-2",
  extractionInputWrap: "flex-1",
  extractionInputLabel: "block text-xs font-semibold text-[#9fb4d2]",
  extractionInput:
    "mt-1 w-full rounded-md border border-[#003566] bg-[#000814]/75 px-3 py-2 text-[#fff8d6] outline-none focus:ring-2 focus:ring-[#ffc300]/30",
  extractionButton:
    "rounded-md bg-[#ffc300] px-4 py-2 font-semibold text-[#000814] hover:bg-[#ffd60a] disabled:opacity-60",
  activationWarning: "text-[#ffd60a]",
  activityListPanel:
    "mt-3 space-y-2 rounded-md border border-[#003566] bg-[#000814]/55 p-3",
  activityListTitle: "font-semibold text-[#ffd60a]",
  activityMeta: "mt-1 space-y-1 text-[#9fb4d2]",
  activityCard:
    "rounded border border-[#003566] bg-[#000814]/70 p-2 text-xs text-[#dbeafe]",
  inlineError: "mt-2 text-[#ffb4b4]",
};

export const cyclistSelectorStyles = {
  container: "space-y-2",
  label: "block text-sm font-semibold text-[#fff8d6]",
  loading: "text-sm text-[#9fb4d2]",
  error: "text-sm text-red-500",
  select:
    "w-full px-3 py-2 bg-[#000814]/75 text-[#fff8d6] border-2 border-[#003566] rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-[#ffc300]/30 focus:border-[#ffc300]",
  option: "bg-[#000814] text-[#fff8d6]",
  hiddenPlaceholder: "hidden",
};

export const authPageStyles = {
  wrapper: "mx-auto max-w-md",
  title: "text-3xl font-bold text-[#ffd60a]",
  subtitle: "mt-2 text-[#dbeafe]/80",
  errorBox:
    "mt-4 rounded-md border border-[#ffc300]/20 bg-[#000814]/70 p-3 text-sm text-[#ffb4b4]",
  form: "mt-6 space-y-4",
  submitButton: "w-full",
  switchText: "mt-6 text-sm text-[#dbeafe]/80",
  switchLink: "font-semibold text-[#ffd60a] hover:underline",
};
