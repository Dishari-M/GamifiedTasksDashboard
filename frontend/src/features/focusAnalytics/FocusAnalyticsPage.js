import { useMemo, useState } from "react";
import { NavLink } from "react-router-dom";
import { CalendarBlank, ChartLineUp, Clock, Fire, Lightbulb, TrendUp, Trophy } from "@phosphor-icons/react";
import { formatMinutes } from "../../utils/dateTime";
import { buildFocusAnalytics, FOCUS_ANALYTICS_PERIODS } from "./focusAnalytics";

const CHART_COLORS = ["#7bb7ff", "#9bd7b1", "#f3c96b", "#c8a7ff", "#f28b82", "#67d7e5"];

const AnalyticsStatCard = ({ label, value, detail, icon: Icon, testId }) => (
  <article className="surface focus-analytics-stat" data-testid={testId}>
    <div className="focus-analytics-stat-head">
      <span>{label}</span>
      <Icon size={24} weight="duotone" aria-hidden="true" />
    </div>
    <strong>{value}</strong>
    <p>{detail}</p>
  </article>
);

const ChartPanel = ({ title, summary, children, testId }) => (
  <section className="surface focus-analytics-chart" data-testid={testId}>
    <div className="section-heading focus-analytics-chart-heading">
      <h2>{title}</h2>
    </div>
    <p className="focus-analytics-chart-summary">{summary}</p>
    <div className="focus-analytics-chart-frame" role="img" aria-label={`${title}. ${summary}`} tabIndex={0}>
      {children}
    </div>
  </section>
);

const NoChartData = ({ message = "No chart data for this period yet." }) => (
  <div className="focus-chart-empty" data-testid="focus-chart-empty">{message}</div>
);

const chartValue = (item, valueKey) => Math.max(0, Number(item?.[valueKey]) || 0);

const SvgText = ({ x, y, children, anchor = "middle", className = "focus-chart-label" }) => (
  <text x={x} y={y} textAnchor={anchor} className={className}>{children}</text>
);

const LineTrendChart = ({ data, valueKey = "minutes", unit = "min", color = CHART_COLORS[0] }) => {
  const values = data.map((item) => chartValue(item, valueKey));
  const max = Math.max(1, ...values);
  const hasData = values.some((value) => value > 0);
  if (!hasData) return <NoChartData message={`No ${unit === "XP" ? "XP" : "focus"} trend data in this period.`} />;

  const width = 640;
  const height = 250;
  const left = 46;
  const right = 18;
  const top = 18;
  const bottom = 42;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const points = data.map((item, index) => {
    const x = left + (data.length === 1 ? plotWidth / 2 : (index / (data.length - 1)) * plotWidth);
    const y = top + plotHeight - (chartValue(item, valueKey) / max) * plotHeight;
    return { x, y, item };
  });
  const pointString = points.map((point) => `${point.x},${point.y}`).join(" ");
  const areaString = `${left},${top + plotHeight} ${pointString} ${left + plotWidth},${top + plotHeight}`;
  const labelEvery = Math.max(1, Math.ceil(data.length / 6));

  return (
    <svg className="native-focus-chart" viewBox={`0 0 ${width} ${height}`} aria-hidden="true" focusable="false">
      {[0, 0.5, 1].map((ratio) => {
        const y = top + plotHeight - ratio * plotHeight;
        return <line key={ratio} className="focus-chart-grid-line" x1={left} x2={left + plotWidth} y1={y} y2={y} />;
      })}
      <SvgText x={left - 12} y={top + 4} anchor="end">{max} {unit}</SvgText>
      <SvgText x={left - 12} y={top + plotHeight + 4} anchor="end">0</SvgText>
      <polygon points={areaString} fill={color} opacity="0.16" />
      <polyline points={pointString} fill="none" stroke={color} strokeWidth="4" strokeLinejoin="round" strokeLinecap="round" />
      {points.map((point) => <circle key={`${point.item.date || point.item.label}-${point.x}`} cx={point.x} cy={point.y} r="4.5" fill={color} stroke="#101521" strokeWidth="2" />)}
      {points.filter((_, index) => index % labelEvery === 0 || index === points.length - 1).map((point) => (
        <SvgText key={`label-${point.item.date || point.item.label}`} x={point.x} y={height - 14}>{point.item.label}</SvgText>
      ))}
    </svg>
  );
};

const BarMetricChart = ({ data, valueKey = "minutes", unit = "min", color = CHART_COLORS[1], emptyMessage }) => {
  const filteredData = data.length ? data : [];
  const values = filteredData.map((item) => chartValue(item, valueKey));
  const max = Math.max(1, ...values);
  const hasData = values.some((value) => value > 0);
  if (!hasData) return <NoChartData message={emptyMessage || "No bar chart data in this period."} />;

  const width = 640;
  const height = 250;
  const left = 44;
  const right = 18;
  const top = 18;
  const bottom = 48;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const gap = 10;
  const barWidth = Math.max(12, (plotWidth - gap * Math.max(0, filteredData.length - 1)) / filteredData.length);
  const labelEvery = Math.max(1, Math.ceil(filteredData.length / 6));

  return (
    <svg className="native-focus-chart" viewBox={`0 0 ${width} ${height}`} aria-hidden="true" focusable="false">
      {[0, 0.5, 1].map((ratio) => {
        const y = top + plotHeight - ratio * plotHeight;
        return <line key={ratio} className="focus-chart-grid-line" x1={left} x2={left + plotWidth} y1={y} y2={y} />;
      })}
      <SvgText x={left - 12} y={top + 4} anchor="end">{max} {unit}</SvgText>
      {filteredData.map((item, index) => {
        const value = chartValue(item, valueKey);
        const barHeight = Math.max(2, (value / max) * plotHeight);
        const x = left + index * (barWidth + gap);
        const y = top + plotHeight - barHeight;
        return (
          <g key={item.week || item.date || item.label}>
            <rect className="focus-chart-bar" x={x} y={y} width={barWidth} height={barHeight} rx="7" fill={color} />
            {filteredData.length <= 8 && value > 0 && <SvgText x={x + barWidth / 2} y={Math.max(12, y - 7)}>{value}</SvgText>}
            {(index % labelEvery === 0 || index === filteredData.length - 1) && <SvgText x={x + barWidth / 2} y={height - 18}>{item.label}</SvgText>}
          </g>
        );
      })}
    </svg>
  );
};

const DonutMetricChart = ({ data, unit = "min", formatter = (value) => value, emptyMessage }) => {
  const total = data.reduce((sum, item) => sum + chartValue(item, "value"), 0);
  if (total <= 0) return <NoChartData message={emptyMessage || "No breakdown data in this period."} />;

  const radius = 72;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;

  return (
    <div className="focus-donut-layout">
      <svg className="native-focus-donut" viewBox="0 0 220 220" aria-hidden="true" focusable="false">
        <circle cx="110" cy="110" r={radius} fill="none" stroke="rgba(137,145,163,0.18)" strokeWidth="28" />
        {data.map((item, index) => {
          const value = chartValue(item, "value");
          const length = (value / total) * circumference;
          const segment = (
            <circle
              key={item.name}
              cx="110"
              cy="110"
              r={radius}
              fill="none"
              stroke={CHART_COLORS[index % CHART_COLORS.length]}
              strokeWidth="28"
              strokeDasharray={`${Math.max(0, length - 4)} ${circumference}`}
              strokeDashoffset={-offset}
              strokeLinecap="round"
              transform="rotate(-90 110 110)"
            />
          );
          offset += length;
          return segment;
        })}
        <text x="110" y="104" textAnchor="middle" className="focus-donut-value">{formatter(total)}</text>
        <text x="110" y="128" textAnchor="middle" className="focus-donut-label">{unit}</text>
      </svg>
      <ul className="focus-chart-legend">
        {data.map((item, index) => (
          <li key={item.name}>
            <span className="focus-chart-swatch" style={{ background: CHART_COLORS[index % CHART_COLORS.length] }} />
            <strong>{item.name}</strong>
            <em>{formatter(item.value)}</em>
          </li>
        ))}
      </ul>
    </div>
  );
};

const EmptyAnalyticsState = () => (
  <section className="surface focus-analytics-empty" data-testid="focus-analytics-empty-state">
    <Clock size={42} weight="duotone" aria-hidden="true" />
    <h2>Focus analytics unlock after your first saved session.</h2>
    <p>Start a Focus session, stop and save it, then come back here to see trends, streaks, and XP patterns.</p>
    <NavLink className="primary-action" to="/focus">Start focus</NavLink>
  </section>
);

const AnalyticsErrorState = () => (
  <section className="surface focus-analytics-empty" role="alert" data-testid="focus-analytics-error-state">
    <Lightbulb size={42} weight="duotone" aria-hidden="true" />
    <h2>Analytics could not be prepared.</h2>
    <p>One of the locally saved focus records could not be read. Your focus data is still available on the Focus page.</p>
    <NavLink className="ghost-button" to="/focus">Back to Focus</NavLink>
  </section>
);

const FocusAnalyticsPage = ({ tasks = [], focusSessions = [] }) => {
  const [periodDays, setPeriodDays] = useState(30);
  const analyticsResult = useMemo(() => {
    try {
      return { data: buildFocusAnalytics({ tasks, focusSessions, periodDays }) };
    } catch {
      return { error: true };
    }
  }, [focusSessions, periodDays, tasks]);

  if (analyticsResult.error) return <main className="page-stack focus-analytics-page" data-testid="focus-analytics-page"><AnalyticsErrorState /></main>;

  const analytics = analyticsResult.data;
  const { stats, insights } = analytics;
  const dateRangeLabel = `${analytics.range.start} to ${analytics.range.end}`;
  const dailySummary = `${analytics.dailyRows.filter((row) => row.minutes > 0).length} active day(s), ${formatMinutes(stats.totalMinutes)} total.`;
  const weeklySummary = analytics.weeklyRows.length ? `${analytics.weeklyRows.length} week bucket(s) in range.` : "No weekly focus yet.";
  const xpSummary = stats.totalXp ? `${stats.totalXp} XP earned: ${stats.baseXp} base and ${stats.focusBonusXp} focus bonus.` : "No earned XP in this period yet.";
  const depthSummary = analytics.focusDepth.length ? analytics.focusDepth.map((item) => `${item.name}: ${formatMinutes(item.value)}`).join(", ") : "No focus depth data yet.";

  return (
    <main className="page-stack focus-analytics-page" data-testid="focus-analytics-page">
      <section className="surface focus-analytics-hero" data-testid="focus-analytics-hero">
        <div>
          <span className="quest-eyebrow">Focus Analytics</span>
          <h1>Understand where your deep work is compounding.</h1>
          <p>{dateRangeLabel}. Metrics are derived from saved focus sessions and completed-task XP.</p>
        </div>
        <div className="focus-analytics-actions">
          <div className="focus-period-control" role="group" aria-label="Focus analytics period">
            {FOCUS_ANALYTICS_PERIODS.map((period) => (
              <button
                key={period.value}
                type="button"
                className={periodDays === period.value ? "active" : ""}
                onClick={() => setPeriodDays(period.value)}
                aria-pressed={periodDays === period.value}
                data-testid={`focus-analytics-period-${period.value}`}
              >
                {period.label}
              </button>
            ))}
          </div>
          <NavLink className="ghost-button" to="/focus" data-testid="focus-analytics-back-link">Back to Focus</NavLink>
        </div>
      </section>

      {stats.isEmpty ? <EmptyAnalyticsState /> : (
        <>
          {stats.insufficientData && (
            <section className="surface focus-analytics-note" data-testid="focus-analytics-insufficient-data">
              <Lightbulb size={24} weight="duotone" aria-hidden="true" />
              <p>Trends need at least two active focus days. The totals below are accurate; comparisons will get more useful as you save more sessions.</p>
            </section>
          )}

          <section className="focus-analytics-stat-grid" aria-label="Focus analytics key metrics">
            <AnalyticsStatCard label="Focus Time" value={stats.totalFocusLabel} detail={stats.improvementLabel} icon={Clock} testId="focus-analytics-total-time" />
            <AnalyticsStatCard label="Sessions" value={stats.completedSessions} detail={`${formatMinutes(stats.averageSessionMinutes)} average length`} icon={ChartLineUp} testId="focus-analytics-session-count" />
            <AnalyticsStatCard label="Consistency" value={`${stats.consistencyPercent}%`} detail={`${stats.activeDays} active day(s), ${stats.currentStreak} day streak`} icon={Fire} testId="focus-analytics-consistency" />
            <AnalyticsStatCard label="XP Earned" value={`${stats.totalXp} XP`} detail={`${stats.focusBonusXp} XP from focus bonus`} icon={Trophy} testId="focus-analytics-xp" />
          </section>

          <section className="focus-analytics-grid">
            <ChartPanel title="Daily Focus Trend" summary={dailySummary} testId="focus-analytics-daily-chart">
              <LineTrendChart data={analytics.dailyRows} valueKey="minutes" unit="min" color={CHART_COLORS[0]} />
            </ChartPanel>

            <ChartPanel title="Weekly Focus" summary={weeklySummary} testId="focus-analytics-weekly-chart">
              <BarMetricChart data={analytics.weeklyRows} valueKey="minutes" unit="min" color={CHART_COLORS[1]} emptyMessage="No weekly focus data in this period." />
            </ChartPanel>

            <ChartPanel title="XP Over Time" summary={xpSummary} testId="focus-analytics-xp-chart">
              <BarMetricChart data={analytics.dailyRows.filter((row) => row.xp > 0)} valueKey="xp" unit="XP" color={CHART_COLORS[2]} emptyMessage="No earned XP in this period yet." />
            </ChartPanel>

            <ChartPanel title="Focus Depth" summary={depthSummary} testId="focus-analytics-depth-chart">
              <DonutMetricChart data={analytics.focusDepth} unit="minutes" formatter={formatMinutes} emptyMessage="Save focus sessions to classify deep and light focus." />
            </ChartPanel>

            <ChartPanel title="Best Focus Window" summary={insights.bestWindow} testId="focus-analytics-window-chart">
              <BarMetricChart data={analytics.focusWindows} valueKey="minutes" unit="min" color={CHART_COLORS[3]} emptyMessage="No focus windows detected yet." />
            </ChartPanel>

            <ChartPanel title="XP Sources" summary={xpSummary} testId="focus-analytics-xp-breakdown-chart">
              <DonutMetricChart data={analytics.xpBreakdown} unit="XP" formatter={(value) => `${value} XP`} emptyMessage="Complete focused tasks to see XP sources." />
            </ChartPanel>
          </section>

          <section className="surface focus-analytics-insights" data-testid="focus-analytics-insights">
            <div className="section-heading">
              <h2><TrendUp size={26} weight="duotone" aria-hidden="true" /> Actionable Insights</h2>
              <span>{dateRangeLabel}</span>
            </div>
            <div className="focus-insight-grid">
              {[insights.bestDay, insights.mostConsistentDay, insights.bestXpDay, insights.improvement].map((insight) => (
                <article key={insight}>
                  <CalendarBlank size={22} weight="duotone" aria-hidden="true" />
                  <p>{insight}</p>
                </article>
              ))}
            </div>
          </section>
        </>
      )}
    </main>
  );
};

export default FocusAnalyticsPage;
