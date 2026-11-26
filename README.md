# Adaptive Workload-Aware Index Tuning for PostgreSQL

An adaptive database index tuning system that analyzes SQL workloads, generates candidate indexes, estimates their performance benefits, and selects an optimized index configuration under storage and workload constraints.

## Overview

Database indexes improve query performance by reducing the amount of data PostgreSQL needs to scan. However, creating too many indexes introduces additional storage requirements and increases the computational overhead of write operations such as `INSERT`, `UPDATE`, and `DELETE`.

This project develops a workload-aware index tuning framework for PostgreSQL that aims to balance read performance, write-maintenance overhead, storage consumption, and the cost of reconfiguration.

Unlike static indexing approaches, the system considers workload characteristics and supports adapting the index configuration when the workload changes.

## Key Features

- **SQL Workload Analysis:** Parses SQL queries and identifies relevant columns from `WHERE`, `JOIN`, `ORDER BY`, and `GROUP BY` clauses.
- **Candidate Index Generation:** Generates single-column and composite index candidates, with composite indexes supporting up to three columns.
- **Candidate Pruning:** Reduces the candidate search space before optimization.
- **Hypothetical Index Evaluation:** Uses HypoPG to estimate query plans and index storage requirements without physically creating every candidate index.
- **Constraint-Based Optimization:** Uses Google OR-Tools CP-SAT to select an index configuration while respecting a storage budget.
- **Read/Write Cost Balancing:** Considers query performance improvements alongside write-maintenance and storage costs.
- **Workload Adaptation:** Detects workload changes using structural drift and incorporates hysteresis to avoid unnecessary index reconfiguration.
- **Experimental Validation:** Evaluates selected configurations using actual PostgreSQL indexes, `EXPLAIN ANALYZE`, and repeated query execution.

## System Architecture

The framework follows the pipeline below:

```text
        SQL Workload
             |
             v
      Workload Analysis
             |
             v
       SQL Parsing
          SQLGlot
             |
             v
   Candidate Index Generation
             |
             v
      Candidate Pruning
             |
             v
   Hypothetical Index Evaluation
            HypoPG
             |
             v
    Index Selection Optimization
          OR-Tools CP-SAT
             |
             v
      Adaptive Decision Engine
             |
             v
      PostgreSQL Indexes
       CREATE / DROP / KEEP
             |
             v
      Performance Evaluation
```

## Optimization Methodology

### 1. Workload Collection and Analysis

SQL workloads are analyzed to identify frequently accessed tables and columns.

The parser extracts relevant attributes from:

- `WHERE` predicates
- `JOIN` conditions
- `ORDER BY` clauses
- `GROUP BY` clauses

This information forms the basis for generating potential index configurations.

### 2. Candidate Index Generation

The system generates candidate single-column and composite indexes.

Composite candidates contain up to three columns. Candidate pruning is applied to restrict the search space to a maximum of 20 candidates for the optimization stage.

### 3. Hypothetical Index Evaluation

HypoPG is used to evaluate hypothetical indexes without physically materializing every candidate.

The PostgreSQL query planner provides estimated execution plans and associated costs, while hypothetical index information is used to estimate storage requirements.

This allows the framework to explore possible index configurations with reduced physical experimentation overhead.

### 4. Index Selection Optimization

The index selection problem is formulated as a binary optimization problem.

A binary decision variable represents whether a candidate index is selected:

- \(x_i = 1\): Index \(i\) is selected.
- \(x_i = 0\): Index \(i\) is not selected.

The optimization framework considers:

- Query performance benefits
- Write-maintenance overhead
- Index storage requirements
- Index reconfiguration costs
- Interactions between selected indexes

Google OR-Tools CP-SAT is used to solve the constrained selection problem.

The experimental configuration uses a storage budget of 500 MB.

### 5. Workload Adaptation

The framework monitors changes in workload structure and evaluates whether the existing index configuration remains suitable.

A structural drift measure is used to identify changes in workload characteristics. Hysteresis is incorporated into the adaptation mechanism to prevent unnecessary or frequent index changes.

The decision engine determines whether an index should be:

- **Created:** When a new index is beneficial.
- **Dropped:** When an existing index is no longer useful.
- **Kept:** When the current configuration remains appropriate.

### 6. Experimental Evaluation

The selected index configuration is physically implemented in PostgreSQL and evaluated using actual query execution.

The experimental procedure includes:

1. Applying the selected indexes.
2. Running `ANALYZE` to update database statistics.
3. Inspecting execution plans using `EXPLAIN ANALYZE`.
4. Performing a warm-up execution.
5. Running three measured executions.
6. Reporting the median execution time.

The evaluation considers query execution time, index storage, write overhead, and index configuration changes.

## Experimental Workloads

The project uses three SQL workload files:

| Workload | Composition |
|---|---|
| `workload_1.sql` | 50 SELECT queries |
| `workload_2.sql` | 30 SELECT queries |
| `workload_3.sql` | 6 write queries |

The workloads are used to study indexing behavior under different query and operation characteristics.

## Initial Experimental Results

An initial experimental configuration produced the following observations:

| Metric | Result |
|---|---:|
| Number of selected indexes | 14 |
| Total index storage | 29.59 MB |
| Baseline execution time | 4018.34 ms |
| Indexed execution time | 2786.34 ms |
| Execution-time reduction | 30.66% |
| Estimated plan cost | 243429.79 |

The observed execution-time reduction is calculated as:

\[
\text{Improvement} =
\frac{T_{\text{baseline}}-T_{\text{indexed}}}
{T_{\text{baseline}}}\times100
\]

These values represent an experimental configuration, rather than a universal performance guarantee. Actual improvements depend on the database, workload, hardware, and query distribution.

## Installation and Setup

### Prerequisites

- Python 3.x
- PostgreSQL
- HypoPG extension
- Required Python packages

### Python Dependencies

```bash
pip install psycopg2-binary sqlglot \
    ortools pandas numpy matplotlib
```

### Database Configuration

Create a PostgreSQL database and enable the HypoPG extension:

```sql
CREATE EXTENSION IF NOT EXISTS hypopg;
```

Configure the database connection parameters in the project's configuration file.

### Running the Project

Run the workload analysis, candidate generation, optimization, and evaluation components according to the project scripts.

Refer to the source files and configuration settings for the execution sequence.
