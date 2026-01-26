import { useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { useTheme } from "@mui/material/styles";
import { Typography, Box } from "@mui/material";
import type { Results } from "../types/types";

interface GraphProps {
  results: Results[];
}

export default function Graph({ results }: GraphProps) {
  const theme = useTheme();

  // Calculate Average Error per Iteration dynamically
  const chartData = useMemo(() => {
    if (results.length === 0) return [];

    // Find the max number of iterations across all results
    const maxIterations = Math.max(...results.map((r) => r.iterations.length));

    return Array.from({ length: maxIterations }, (_, i) => {
      const currentIterNum = i + 1;

      // Get error rates for this specific iteration across all claims
      const errorsAtStep = results.map((r) => {
        const iter = r.iterations.find((it) => it.iteration === currentIterNum);

        // If this iteration exists, calculate error % vs ground truth
        if (iter && r.ground_truth > 0) {
          const diff = Math.abs(iter.estimate - r.ground_truth);
          return (diff / r.ground_truth) * 100;
        }
        return 0; // fallback if no iteration or div by zero
      });

      // Calculate Average for the graph point
      const avgError =
        errorsAtStep.length > 0 ? errorsAtStep.reduce((a, b) => a + b, 0) / errorsAtStep.length : 0;

      return {
        name: `Iter ${currentIterNum}`,
        ErrorRate: parseFloat(avgError.toFixed(1)),
      };
    });
  }, [results]);

  if (results.length === 0) {
    return <Typography color="text.secondary">No data to display</Typography>;
  }

  return (
    <Box sx={{ width: "100%", height: "100%", minHeight: 300 }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} />
          <XAxis
            dataKey="name"
            tick={{ fill: theme.palette.text.secondary, fontSize: 12 }}
            tickLine={false}
          />
          <YAxis
            label={{
              value: "Avg Error %",
              angle: -90,
              position: "insideLeft",
              fill: theme.palette.text.secondary,
            }}
            tick={{ fill: theme.palette.text.secondary, fontSize: 12 }}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: theme.palette.background.paper,
              border: `1px solid ${theme.palette.divider}`,
              borderRadius: "4px",
            }}
          />
          <Legend />
          <Line
            type="monotone"
            dataKey="ErrorRate"
            name="Error Rate %"
            stroke={theme.palette.primary.main}
            strokeWidth={3}
            activeDot={{ r: 6 }}
            dot={{ r: 4, fill: theme.palette.primary.main }}
          />
        </LineChart>
      </ResponsiveContainer>
    </Box>
  );
}
