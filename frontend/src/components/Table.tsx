import React, { useState } from "react";
import {
  Box,
  Collapse,
  IconButton,
  Table as MuiTable,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  Chip,
  Paper,
} from "@mui/material";
import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import KeyboardArrowUpIcon from "@mui/icons-material/KeyboardArrowUp";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import ErrorIcon from "@mui/icons-material/Error";
import type { Results } from "../types/types";

// --- Sub-component for individual rows ---
function Row({ row }: { row: Results }) {
  const [open, setOpen] = useState(false);

  // Derive final estimate from the last iteration
  const finalIteration = row.iterations[row.iterations.length - 1];
  const finalEstimate = finalIteration ? finalIteration.estimate : 0;

  const diff = finalEstimate - row.ground_truth;
  // Consider it a "Match" if difference is negligible (floating point safety)
  const isMatch = Math.abs(diff) < 0.01;

  return (
    <React.Fragment>
      <TableRow sx={{ "& > *": { borderBottom: "unset" } }} hover>
        {/* Expand Button */}
        <TableCell width={50}>
          <IconButton aria-label="expand row" size="small" onClick={() => setOpen(!open)}>
            {open ? <KeyboardArrowUpIcon /> : <KeyboardArrowDownIcon />}
          </IconButton>
        </TableCell>

        {/* Main Data Columns */}
        <TableCell component="th" scope="row" sx={{ fontWeight: "bold" }}>
          {row.tracking_number}
        </TableCell>
        <TableCell align="right">${row.ground_truth?.toLocaleString()}</TableCell>
        <TableCell align="right" sx={{ fontWeight: "bold" }}>
          ${finalEstimate.toLocaleString()}
        </TableCell>
        <TableCell
          align="right"
          sx={{
            color: isMatch ? "success.main" : "error.main",
            fontWeight: "medium",
          }}
        >
          {diff > 0 ? "+" : ""}
          {diff.toLocaleString()}
        </TableCell>
        <TableCell align="center">
          {isMatch ? (
            <Chip
              icon={<CheckCircleIcon />}
              label="Match"
              color="success"
              size="small"
              variant="outlined"
            />
          ) : (
            <Chip
              icon={<ErrorIcon />}
              label="Variance"
              color="warning"
              size="small"
              variant="outlined"
            />
          )}
        </TableCell>
      </TableRow>

      {/* Expanded Detail View */}
      <TableRow>
        <TableCell style={{ paddingBottom: 0, paddingTop: 0 }} colSpan={6}>
          <Collapse in={open} timeout="auto" unmountOnExit>
            <Box sx={{ margin: 2 }}>
              <Typography variant="subtitle2" gutterBottom component="div" color="primary">
                AI Reasoning History
              </Typography>
              <TableContainer component={Paper} variant="outlined" sx={{ mb: 2 }}>
                <MuiTable size="small" aria-label="iterations">
                  <TableHead>
                    <TableRow sx={{ backgroundColor: "action.hover" }}>
                      <TableCell>Step</TableCell>
                      <TableCell align="right">Estimate</TableCell>
                      <TableCell>Reasoning</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {row.iterations.map((iter) => (
                      <TableRow key={iter.iteration}>
                        <TableCell component="th" scope="row" width={80}>
                          Iter {iter.iteration}
                        </TableCell>
                        <TableCell align="right" width={120}>
                          ${iter.estimate.toLocaleString()}
                        </TableCell>
                        <TableCell sx={{ color: "text.secondary", fontSize: "0.875rem" }}>
                          {iter.reasoning}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </MuiTable>
              </TableContainer>
            </Box>
          </Collapse>
        </TableCell>
      </TableRow>
    </React.Fragment>
  );
}

// --- Main Table Component ---
interface TableProps {
  results: Results[];
}

export default function Table({ results }: TableProps) {
  if (!results || results.length === 0) return null;

  return (
    <TableContainer>
      <MuiTable aria-label="collapsible table">
        <TableHead>
          <TableRow>
            <TableCell />
            <TableCell>ID</TableCell>
            <TableCell align="right">Ground Truth</TableCell>
            <TableCell align="right">AI Final</TableCell>
            <TableCell align="right">Difference</TableCell>
            <TableCell align="center">Status</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {results.map((row) => (
            <Row key={row.tracking_number} row={row} />
          ))}
        </TableBody>
      </MuiTable>
    </TableContainer>
  );
}
