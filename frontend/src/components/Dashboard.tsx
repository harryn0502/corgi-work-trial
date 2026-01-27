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
} from "@mui/material";
import Grid from "@mui/material/Grid";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import AnalyticsIcon from "@mui/icons-material/Analytics";

import api from "../api";
import Table from "./Table";
import Graph from "./Graph";
import type { Results } from "../types/types";

interface FormInputs {
  tracking_numbers: string;
  iteration_count: number;
}

export default function Dashboard() {
  const [results, setResults] = useState<Results[]>([]);
  const [loading, setLoading] = useState(false);

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

  const onSubmit: SubmitHandler<FormInputs> = async (data) => {
    setLoading(true);
    setResults([]);
    try {
      const res = await api.post("/api/analyze/", {
        tracking_numbers: data.tracking_numbers,
        iteration_count: data.iteration_count,
      });
      setResults(res.data);
    } catch (error) {
      console.error(error);
      alert("Failed analyzing. Check backend console for details.");
    } finally {
      setLoading(false);
    }
  };

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
