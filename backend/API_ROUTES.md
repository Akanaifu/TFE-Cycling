# TFE Cycling Backend API Routes

## Overview

This backend provides REST endpoints for running HR/power prediction models on cycling rides from PKL files.

## Path Conventions

Paths in requests can be:

- **Relative**: Resolved from the backend directory. Example: `../../notebook/rides/cyclist9`
- **Absolute**: Full filesystem path

## Routes

### 1. Health & Status

#### `GET /`

Returns API status.

```json
{ "message": "TFE Cycling backend is running" }
```

#### `GET /health`

Health check endpoint.

```json
{ "status": "ok" }
```

---

### 2. Ride Management

#### `GET /rides/list`

List all rides available in a directory.

**Query Parameters:**

- `dir_path` (required): Directory containing PKL files

**Example Request:**

```
GET /rides/list?dir_path=../../notebook/rides/cyclist9
```

**Response:**

```json
{
  "ok": true,
  "dir_path": "../../notebook/rides/cyclist9",
  "n_rides": 5,
  "rides": [
    {
      "index": 1,
      "datetime": "02/04/2026 09:56:36",
      "points": 1250,
      "columns": ["t", "hr", "po", "t_min", "work", "work2", "work3", "work4", "po_lag_1", ...]
    },
    ...
  ]
}
```

---

### 3. Pipeline Execution

#### `POST /pipeline/run`

Execute the full ML pipeline and return rides with predictions.

**Request Body:**

```json
{
  "dir_path": "../../notebook/rides/cyclist9",
  "selected_models_compute": ["pred_arx_selected"],
  "prev_ride": 1,
  "nan_ratio": 1.0,
  "selected_train_ride": 1,
  "selected_target_rides": null
}
```

**Parameters:**

- `dir_path` (required): Directory containing rides to analyze
- `selected_models_compute` (default: ["pred_arx_selected"]): Which models to compute
  - Available models: `pred_hist`, `pred_default`, `pred_no_fuite`, `pred_arx_selected`
- `prev_ride` (default: 1): Index of previous ride for ARX models
- `nan_ratio` (default: 1.0): Maximum NaN ratio tolerance (0-1)
- `selected_train_ride` (default: 1): Training ride index (1-based)
- `selected_target_rides` (default: null): Target ride indices, null means all except training

**Response:**

```json
{
  "ok": true,
  "n_rides": 5,
  "models_requested": ["pred_arx_selected"],
  "models_computed": ["pred_arx_selected"],
  "rides": [
    {
      "datetime": "02/04/2026 09:56:36",
      "n_points": 1250,
      "columns": ["t", "hr", "po", "t_min", "work", "work2", "work3", "work4", "po_lag_*", "pred_arx_selected"],
      "data": [
        {"t": 0, "hr": 60, "po": 0, "t_min": 0.0, ..., "pred_arx_selected": 61.5},
        {"t": 1, "hr": 62, "po": 150, "t_min": 0.016..., ..., "pred_arx_selected": 62.3},
        ...
      ]
    },
    ...
  ]
}
```

---

### 4. Analysis Summary

#### `POST /analysis/run`

Execute analysis and get summary statistics (RMSE metrics, data summaries).

**Request Body:**

```json
{
  "dir_path": "../../notebook/rides/cyclist9",
  "selected_models_plot": ["pred_arx_selected"],
  "selected_models_stats": ["pred_arx_selected"],
  "show_rmse_table": true,
  "prev_ride": 1,
  "nan_ratio": 1.0,
  "selected_train_ride": 1,
  "selected_target_rides": null
}
```

**Response:**

```json
{
  "n_rides": 5,
  "selected_models_compute": ["pred_arx_selected"],
  "rmse_table": [
    {"ride": "Ride 1", "pred_arx_selected": 3.45},
    ...
  ],
  "model_data_summary": [
    {"model": "pred_arx_selected", "valid_points": 6200},
    ...
  ]
}
```

---

### 5. PKL File Testing

#### `GET /pkl/test-read`

Test if a PKL file is readable (GET variant).

**Query Parameters:**

- `file_path` (required): Path to PKL file

**Example Request:**

```
GET /pkl/test-read?file_path=../../notebook/rides/cyclist9/2026-04-02T09_56_36.000000000.pkl
```

**Response:**

```json
{
  "ok": true,
  "file_path": "/absolute/path/to/file.pkl",
  "type": "DataFrame",
  "rows": 1250,
  "columns": ["t", "hr", "po"]
}
```

#### `POST /pkl/test-read`

Test if a PKL file is readable (POST variant).

**Request Body:**

```json
{
  "file_path": "../../notebook/rides/cyclist9/2026-04-02T09_56_36.000000000.pkl"
}
```

**Response:**
Same as GET variant.

---

## Model Descriptions

### Available Prediction Models

1. **`pred_hist`** - Historical prediction using previous rides
2. **`pred_default`** - Default linear regression on individual rides
3. **`pred_no_fuite`** - ARX model without data leakage (no future power information)
4. **`pred_arx_selected`** - ARX model trained on a specific ride with lagged inputs

---

## Example Workflows

### Workflow 1: List available cyclist data

```bash
curl -X GET "http://localhost:8000/rides/list?dir_path=../../notebook/rides/cyclist9"
```

### Workflow 2: Run full pipeline with predictions

```bash
curl -X POST "http://localhost:8000/pipeline/run" \
  -H "Content-Type: application/json" \
  -d '{
    "dir_path": "../../notebook/rides/cyclist9",
    "selected_models_compute": ["pred_arx_selected"],
    "selected_train_ride": 1
  }'
```

### Workflow 3: Test PKL file readability

```bash
curl -X GET "http://localhost:8000/pkl/test-read?file_path=../../notebook/rides/cyclist9/2026-04-02T09_56_36.000000000.pkl"
```

### Workflow 4: Get RMSE metrics

```bash
curl -X POST "http://localhost:8000/analysis/run" \
  -H "Content-Type: application/json" \
  -d '{
    "dir_path": "../../notebook/rides/cyclist9",
    "selected_models_stats": ["pred_arx_selected"],
    "selected_train_ride": 1
  }'
```

---

## Error Responses

All errors return HTTP status codes with detail messages:

```json
{
  "detail": "Error description here"
}
```

Common error codes:

- `400`: Invalid request or processing error (bad path, no valid rides, model error)
- `404`: File/directory not found
- `500`: Internal server error
