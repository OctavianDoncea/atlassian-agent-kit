import { Area, AreaChart, Bar, BarChart, CartesianGrid, Rectangle, ResponsiveContainer, Tooltip, XAxis, YAxis, type BarShapeProps } from "recharts";
import type { TimeseriesPoint, VariantStat } from "../api";

const tooltipStyle = { background: '#0f172a', border: '1px solid #334155', borderRadius: 8 };

function variantBar(props: BarShapeProps & { active?: boolean }) {
    return <Rectangle {...props} fill={props.active ? '#34d399' : '#64748b'} />;
}

export function PassRateChart({ data }: { data: TimeseriesPoint[] }) {
    const rows = data.map((d) => ({ ...d, rate: +(d.pass_rate * 100).toFixed(1) }));
    return (
        <div className="h-64">
            <ResponsiveContainer>
                <AreaChart data={rows}>
                    <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
                    <XAxis dataKey="bucket" stroke="#94a3b8" fontSize={10} />
                    <YAxis domain={[0, 100]} stroke="#94a3b8" unit="%" />
                    <Tooltip contentStyle={tooltipStyle} />
                    <Area type="monotone" dataKey="rate" name="pass rate %" stroke="#34d399" fill="#34d39933" /> 
                </AreaChart>
            </ResponsiveContainer>
        </div>
    )
}

export function VariantChart({ stats, tool }: { stats: VariantStat[]; tool: string }) {
    const rows = stats.filter((s) => s.tool_name === tool).map((s) => ({ name: s.variant ?? `v${s.version}`, rate: +(s.pass_rate * 100).toFixed(1), active: s.is_active, trials: s.trials }));
    return (
        <div className="h-64">
            <ResponsiveContainer>
                <BarChart data={rows}>
                    <CartesianGrid stroke='#334155' strokeDasharray='3 3' />
                    <XAxis dataKey='name' stroke='#94a3b8' fontSize={11} />
                    <YAxis domain={[0, 100]} stroke='#94a3b8' fontSize={11} unit='%' />
                    <Tooltip contentStyle={tooltipStyle} />
                    <Bar dataKey="rate" name="pass rate %" shape={variantBar} />
                </BarChart>
            </ResponsiveContainer>
        </div>
    )
}