export type MessageRole = "user" | "assistant" | "system";
export type WidgetType =
  | "kpi"
  | "line_chart"
  | "bar_chart"
  | "pie_chart"
  | "area_chart"
  | "table";

export interface Message {
  id: string;
  session_id: string;
  role: MessageRole;
  content: string;
  created_at: string;
}

export interface DatabaseConnectionSummary {
  id: string;
  name: string;
  database_type: "postgresql";
  database_name: string;
  ssl_mode: string;
}

export interface QueryDefinition {
  id: string;
  name: string;
  sql: string;
  parameters: Record<string, unknown>;
}

export interface WidgetConfig {
  id: string;
  type: WidgetType;
  title: string;
  query_id: string | null;
  x_field: string | null;
  y_fields: string[];
  value_field: string | null;
  options: Record<string, unknown>;
}

export interface LayoutItem {
  widget_id: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface DashboardConfig {
  title: string;
  queries: QueryDefinition[];
  widgets: WidgetConfig[];
  layout: LayoutItem[];
}

export interface DashboardRecord {
  id: string;
  session_id: string;
  title: string;
  config_json: DashboardConfig;
  current_version: number;
  last_modified_by_message_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface SessionSummary {
  id: string;
  user_id: string | null;
  title: string;
  database_connection_id: string | null;
  ai_provider: string | null;
  ai_model: string | null;
  created_at: string;
  updated_at: string;
}

export interface SessionDetails extends SessionSummary {
  messages: Message[];
  database_connection: DatabaseConnectionSummary | null;
  dashboard: DashboardRecord | null;
}

export interface AgentChange {
  type: "CREATE_DASHBOARD" | "MODIFY_DASHBOARD" | "ASK_DATA_QUESTION";
  affected_widgets: string[];
  summary: string | null;
}

export interface AgentMessageResponse {
  message: Message;
  dashboard: DashboardConfig | null;
  dashboard_version: number | null;
  change: AgentChange | null;
}

export interface QueryResult {
  columns: string[];
  rows: Array<Record<string, unknown>>;
  row_count: number;
  truncated: boolean;
  execution_time_ms: number;
}

export interface DashboardData {
  dashboard: DashboardRecord;
  query_results: Record<string, QueryResult>;
}

export interface DatabaseConnectionInput {
  name: string;
  host: string;
  port: number;
  database_name: string;
  username: string;
  password: string;
  ssl_mode: string;
}
