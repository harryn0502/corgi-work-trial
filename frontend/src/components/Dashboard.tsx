import { useState } from "react";
import { useForm, type SubmitHandler } from "react-hook-form";
import {
  Container,
  Paper,
  Typography,
  TextField,
  Button,
  Box,
  CircularProgress,
  Stack,
  LinearProgress,
  CardContent,
  Card,
  Chip,
} from "@mui/material";
import Grid from "@mui/material/Grid";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import AnalyticsIcon from "@mui/icons-material/Analytics";
import UpdateIcon from "@mui/icons-material/Update";

import Table from "./Table";
import Graph from "./Graph";
import type { Results } from "../types/types";

interface FormInputs {
  tracking_numbers: string;
  iteration_count: number;
}

interface StreamStatus {
  totalSteps: number;
  completedSteps: number;
  currentIteration: number;
  lastProcessedId: string;
  lastEstimate: number;
}

export default function Dashboard() {
  const [results, setResults] = useState<Results[]>([]);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<StreamStatus | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormInputs>({
    defaultValues: {
      tracking_numbers: "",
      iteration_count: 3,
    },
  });

  // Helper to merge streaming data to existing results
  const updateResults = (prevResults: Results[], newData: Results) => {
    const existingIndex = prevResults.findIndex(
      (r) => r.tracking_number === newData.tracking_number,
    );

    if (existingIndex >= 0) {
      // Update existing row
      const updated = [...prevResults];
      updated[existingIndex] = newData;
      return updated;
    } else {
      // Add new row
      return [...prevResults, newData];
    }
  };

  const onSubmit: SubmitHandler<FormInputs> = async (data) => {
    setLoading(true);
    setResults([]);

    // Compute the total steps for progress bar
    const trackingIds = data.tracking_numbers.split(",").filter((x) => x.trim());
    const totalSteps = trackingIds.length * data.iteration_count;

    setStatus({
      totalSteps,
      completedSteps: 0,
      currentIteration: 0,
      lastProcessedId: "Starting...",
      lastEstimate: 0,
    });

    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/analyze/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          tracking_numbers: data.tracking_numbers,
          iteration_count: data.iteration_count,
        }),
      });

      if (!response.body) throw new Error("No response body");

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      // Read loop
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        // Decode chunk and add to buffer
        buffer += decoder.decode(value, { stream: true });

        // Split by newline
        const parts = buffer.split("\n");

        // In case last part might be incomplete keep it in the buffer
        buffer = parts.pop() || "";

        for (const part of parts) {
          if (part.trim()) {
            try {
              const jsonChunk: Results = JSON.parse(part);

              // Get latest iteration number for this chunk
              const lastIter = jsonChunk.iterations[jsonChunk.iterations.length - 1];
              const currentIterNum = lastIter ? lastIter.iteration : 1;

              // Update progress state
              setStatus((prev) => {
                if (!prev) return null;
                return {
                  ...prev,
                  completedSteps: prev.completedSteps + 1,
                  currentIteration: currentIterNum,
                  lastProcessedId: jsonChunk.tracking_number,
                  lastEstimate:
                    jsonChunk.iterations[jsonChunk.iterations.length - 1]?.estimate || 0,
                };
              });

              // Update results data
              setResults((prev) => updateResults(prev, jsonChunk));
            } catch (e) {
              console.error("Error parsing JSON chunk:", e);
            }
          }
        }
      }
    } catch (error) {
      console.error(error);
      alert("Stream failed. Check console.");
    } finally {
      setLoading(false);
    }
  };

  // Calculate progress percentage
  const progressPercent = status
    ? Math.min((status.completedSteps / status.totalSteps) * 100, 100)
    : 0;

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      {/* Header & Form Section */}
      <Paper elevation={3} sx={{ p: 4, mb: 4, borderRadius: 2 }}>
        <Box display="flex" alignItems="center" mb={3}>
          <AnalyticsIcon color="primary" sx={{ fontSize: 40, mr: 2 }} />
          <Typography variant="h4" component="h1" fontWeight="bold" color="text.primary">
            Deposit Claim Estimator
          </Typography>
        </Box>

        <Box component="form" onSubmit={handleSubmit(onSubmit)} noValidate>
          {/* Grid2 Container */}
          <Grid container spacing={3} alignItems="flex-start">
            {/* Input: Tracking Numbers */}
            <Grid size={{ xs: 12, md: 8 }}>
              <TextField
                fullWidth
                label="Tracking Number(s)"
                placeholder="e.g. 1, 123, 145"
                variant="outlined"
                {...register("tracking_numbers", { required: "IDs are required" })}
                error={!!errors.tracking_numbers}
                helperText={
                  errors.tracking_numbers?.message || "Enter comma-separated IDs (must match CSV)"
                }
              />
            </Grid>

            {/* Input: Iteration Count */}
            <Grid size={{ xs: 12, md: 2 }}>
              <TextField
                fullWidth
                type="number"
                label="Iterations"
                variant="outlined"
                inputProps={{ min: 1, max: 5 }}
                {...register("iteration_count", {
                  required: "Required",
                  min: { value: 1, message: "Min 1" },
                  max: { value: 5, message: "Max 5" },
                })}
                error={!!errors.iteration_count}
                helperText={errors.iteration_count?.message}
              />
            </Grid>

            {/* Submit Button */}
            <Grid size={{ xs: 12, md: 2 }}>
              <Button
                fullWidth
                type="submit"
                variant="contained"
                size="large"
                disabled={loading}
                startIcon={
                  loading ? <CircularProgress size={20} color="inherit" /> : <PlayArrowIcon />
                }
                sx={{ height: "56px", fontWeight: "bold" }}
              >
                {loading ? "Running..." : "Analyze"}
              </Button>
            </Grid>
          </Grid>
        </Box>
      </Paper>

      {loading && status && (
        <Card variant="outlined" sx={{ mb: 4, borderColor: "primary.main", bgcolor: "#f5f9ff" }}>
          <CardContent>
            <Stack direction="row" spacing={2} alignItems="center" mb={1}>
              <UpdateIcon color="primary" className="spin-animation" />
              <Typography variant="h6" color="primary" fontWeight="bold">
                Processing Cycle: Iteration {status.currentIteration}
              </Typography>
              <Chip label={`Latest: ID #${status.lastProcessedId}`} color="primary" size="small" />
              <Chip
                label={`Est: $${status.lastEstimate.toLocaleString()}`}
                variant="outlined"
                size="small"
              />
            </Stack>

            <Box sx={{ display: "flex", alignItems: "center" }}>
              <Box sx={{ width: "100%", mr: 1 }}>
                <LinearProgress
                  variant="determinate"
                  value={progressPercent}
                  sx={{ height: 10, borderRadius: 5 }}
                />
              </Box>
              <Box sx={{ minWidth: 35 }}>
                <Typography variant="body2" color="text.secondary">
                  {Math.round(progressPercent)}%
                </Typography>
              </Box>
            </Box>
            <Typography variant="caption" color="text.secondary">
              Processed {status.completedSteps} of {status.totalSteps} total operations...
            </Typography>
          </CardContent>
        </Card>
      )}

      {/* Results Section */}
      {results.length > 0 && (
        <Grid container spacing={4}>
          {/* Graph Column */}
          <Grid size={{ xs: 12, lg: 4 }}>
            <Paper elevation={2} sx={{ p: 3, height: 350, borderRadius: 2 }}>
              <Typography variant="h6" gutterBottom fontWeight="bold">
                Error Convergence
              </Typography>
              {/* Fixed height container for Recharts */}
              <Box sx={{ height: 300, mt: 2 }}>
                <Graph results={results} />
              </Box>
            </Paper>
          </Grid>

          {/* Table Column */}
          <Grid size={{ xs: 12, lg: 8 }}>
            <Paper elevation={2} sx={{ p: 3, height: "100%", borderRadius: 2 }}>
              <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
                <Typography variant="h6" fontWeight="bold">
                  Results Breakdown
                </Typography>
                <Typography
                  variant="caption"
                  sx={{
                    bgcolor: "primary.light",
                    color: "primary.contrastText",
                    px: 1.5,
                    py: 0.5,
                    borderRadius: 4,
                  }}
                >
                  {results.length} Claims Processed
                </Typography>
              </Stack>
              <Table results={results} />
            </Paper>
          </Grid>
        </Grid>
      )}
    </Container>
  );
}
