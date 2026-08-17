import { BarChart3, Table2, TrendingUp } from "lucide-react";
import type { CSSProperties } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { LayoutItem, QueryResult, WidgetConfig } from "../types";

interface DashboardWidgetProps {
  widget: WidgetConfig;
  layout: LayoutItem;
  result: QueryResult | undefined;
}

const chartColors = ["#2F4157", "#567C8E", "#A2C1D1", "#C7D9E5"];
const tooltipStyle = {
  border: "1px solid #A2C1D1",
  borderRadius: 6,
  boxShadow: "0 8px 20px rgba(47, 65, 87, 0.12)",
  fontSize: 12,
};

export function DashboardWidget({ widget, layout, result }: DashboardWidgetProps) {
  const style: CSSProperties = {
    gridColumn: `${layout.x + 1} / span ${layout.width}`,
    gridRow: `${layout.y + 1} / span ${layout.height}`,
  };
  const data = result?.rows ?? [];

  return (
    <article style={style} className="flex min-h-[190px] min-w-0 flex-col overflow-hidden rounded-md border border-cloud bg-white p-4 shadow-[0_4px_18px_rgba(47,65,87,0.05)]">
      <header className="mb-3 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="truncate text-sm font-bold text-ink">{widget.title}</h2>
          <p className="mt-0.5 text-xs text-steel">{result ? `${result.row_count} rows` : "No result"}</p>
        </div>
        <WidgetIcon type={widget.type} />
      </header>
      <div className="min-h-0 flex-1">
        {!result ? (
          <div className="grid h-full place-items-center text-sm text-steel">Data unavailable</div>
        ) : widget.type === "kpi" ? (
          <KpiValue value={data[0]?.[widget.value_field ?? ""]} />
        ) : widget.type === "table" ? (
          <TableWidget result={result} />
        ) : widget.type === "pie_chart" ? (
          <ResponsiveContainer width="100%" height="100%" minHeight={130}>
            <PieChart>
              <Pie data={data} dataKey={widget.y_fields[0]} nameKey={widget.x_field ?? undefined} innerRadius="42%" outerRadius="74%" paddingAngle={2}>
                {data.map((_, index) => <Cell key={index} fill={chartColors[index % chartColors.length]} />)}
              </Pie>
              <Tooltip contentStyle={tooltipStyle} />
              <Legend iconSize={8} wrapperStyle={{ fontSize: 11 }} />
            </PieChart>
          </ResponsiveContainer>
        ) : (
          <CartesianWidget widget={widget} data={data} />
        )}
      </div>
    </article>
  );
}

function KpiValue({ value }: { value: unknown }) {
  const display = typeof value === "number" ? new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value) : String(value ?? "-");
  return (
    <div className="flex h-full items-end pb-2">
      <p className="max-w-full break-words text-3xl font-bold text-ink sm:text-4xl">{display}</p>
    </div>
  );
}

function CartesianWidget({ widget, data }: { widget: WidgetConfig; data: Array<Record<string, unknown>> }) {
  const common = (
    <>
      <CartesianGrid stroke="#E3ECF2" vertical={false} />
      <XAxis dataKey={widget.x_field ?? undefined} tick={{ fill: "#567C8E", fontSize: 11 }} axisLine={false} tickLine={false} />
      <YAxis tick={{ fill: "#567C8E", fontSize: 11 }} axisLine={false} tickLine={false} width={40} />
      <Tooltip contentStyle={tooltipStyle} />
      {widget.y_fields.length > 1 && <Legend iconSize={8} wrapperStyle={{ fontSize: 11 }} />}
    </>
  );
  if (widget.type === "bar_chart") {
    return (
      <ResponsiveContainer width="100%" height="100%" minHeight={130}>
        <BarChart data={data} margin={{ top: 6, right: 4, left: -8, bottom: 0 }}>
          {common}
          {widget.y_fields.map((field, index) => <Bar key={field} dataKey={field} fill={chartColors[index % chartColors.length]} radius={[3, 3, 0, 0]} />)}
        </BarChart>
      </ResponsiveContainer>
    );
  }
  if (widget.type === "area_chart") {
    return (
      <ResponsiveContainer width="100%" height="100%" minHeight={130}>
        <AreaChart data={data} margin={{ top: 6, right: 4, left: -8, bottom: 0 }}>
          {common}
          {widget.y_fields.map((field, index) => <Area key={field} type="monotone" dataKey={field} stroke={chartColors[index % chartColors.length]} fill="#C7D9E5" fillOpacity={0.72} />)}
        </AreaChart>
      </ResponsiveContainer>
    );
  }
  return (
    <ResponsiveContainer width="100%" height="100%" minHeight={130}>
      <LineChart data={data} margin={{ top: 6, right: 4, left: -8, bottom: 0 }}>
        {common}
        {widget.y_fields.map((field, index) => <Line key={field} type="monotone" dataKey={field} stroke={chartColors[index % chartColors.length]} strokeWidth={2} dot={{ r: 2 }} />)}
      </LineChart>
    </ResponsiveContainer>
  );
}

function TableWidget({ result }: { result: QueryResult }) {
  return (
    <div className="h-full overflow-auto">
      <table className="w-full min-w-[420px] border-collapse text-left text-xs">
        <thead className="sticky top-0 bg-cloud text-ink">
          <tr>{result.columns.map((column) => <th key={column} className="border-b border-mist px-2.5 py-2 font-bold">{column}</th>)}</tr>
        </thead>
        <tbody>{result.rows.slice(0, 100).map((row, index) => <tr key={index} className="border-b border-cloud last:border-0">{result.columns.map((column) => <td key={column} className="px-2.5 py-2 text-steel">{String(row[column] ?? "")}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}

function WidgetIcon({ type }: { type: WidgetConfig["type"] }) {
  const Icon = type === "table" ? Table2 : type === "kpi" ? TrendingUp : BarChart3;
  return <span className="grid h-7 w-7 shrink-0 place-items-center rounded bg-cloud text-steel"><Icon size={14} /></span>;
}
