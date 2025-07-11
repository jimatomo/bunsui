# Bunsui Sequence Diagrams

## Overview

本ドキュメントでは、Bunsuiシステムにおける主要なユースケースのシーケンス図を示します。

## 1. Pipeline Creation and Execution

### 1.1 Pipeline Definition and Execution

```mermaid
sequenceDiagram
    participant User
    participant TUI
    participant PipelineManager
    participant SessionManager
    participant DynamoDBClient
    participant StepFunctionsClient
    participant S3Client

    User->>TUI: Create Pipeline Request
    TUI->>PipelineManager: Define Pipeline
    PipelineManager->>PipelineManager: Validate DAG Structure
    PipelineManager->>TUI: Pipeline Created
    TUI->>User: Show Pipeline Definition

    User->>TUI: Execute Pipeline
    TUI->>SessionManager: Create Session
    SessionManager->>DynamoDBClient: Store Session Metadata
    DynamoDBClient-->>SessionManager: Session Stored
    SessionManager->>StepFunctionsClient: Start Execution
    StepFunctionsClient-->>SessionManager: Execution Started
    SessionManager->>S3Client: Initialize Log Storage
    S3Client-->>SessionManager: Log Storage Ready
    SessionManager->>TUI: Session Created
    TUI->>User: Show Execution Started
```

### 1.2 Pipeline Execution Monitoring

```mermaid
sequenceDiagram
    participant User
    participant TUI
    participant SessionManager
    participant StepFunctionsClient
    participant DynamoDBClient
    participant S3Client

    User->>TUI: Monitor Pipeline
    TUI->>SessionManager: Get Session Status
    SessionManager->>StepFunctionsClient: Get Execution Status
    StepFunctionsClient-->>SessionManager: Execution Status
    SessionManager->>DynamoDBClient: Update Session State
    DynamoDBClient-->>SessionManager: State Updated
    SessionManager->>S3Client: Retrieve Logs
    S3Client-->>SessionManager: Logs Retrieved
    SessionManager->>TUI: Current Status & Logs
    TUI->>User: Display Real-time Status
```

## 2. Session Management

### 2.1 Session Lifecycle Management

```mermaid
sequenceDiagram
    participant PipelineManager
    participant SessionManager
    participant DynamoDBClient
    participant StepFunctionsClient
    participant S3Client
    participant ErrorHandler

    PipelineManager->>SessionManager: Create Session
    SessionManager->>DynamoDBClient: Store Session (CREATED)
    DynamoDBClient-->>SessionManager: Session Stored

    SessionManager->>StepFunctionsClient: Start Execution
    SessionManager->>DynamoDBClient: Update Status (RUNNING)
    
    alt Successful Execution
        StepFunctionsClient-->>SessionManager: Execution Complete
        SessionManager->>DynamoDBClient: Update Status (COMPLETED)
        SessionManager->>S3Client: Archive Logs
        S3Client-->>SessionManager: Logs Archived
    else Error Occurs
        StepFunctionsClient-->>SessionManager: Execution Failed
        SessionManager->>ErrorHandler: Handle Error
        ErrorHandler->>SessionManager: Recovery Strategy
        SessionManager->>DynamoDBClient: Update Status (FAILED/RETRY)
    end
```

### 2.2 Session Recovery

```mermaid
sequenceDiagram
    participant User
    participant TUI
    participant SessionManager
    participant DynamoDBClient
    participant StepFunctionsClient
    participant ErrorHandler

    User->>TUI: Recover Session
    TUI->>SessionManager: Recover Session Request
    SessionManager->>DynamoDBClient: Get Session State
    DynamoDBClient-->>SessionManager: Session Metadata
    SessionManager->>StepFunctionsClient: Get Execution History
    StepFunctionsClient-->>SessionManager: Execution Details
    SessionManager->>ErrorHandler: Analyze Recovery Options
    ErrorHandler-->>SessionManager: Recovery Plan
    SessionManager->>TUI: Show Recovery Options
    TUI->>User: Display Recovery Options
    
    User->>TUI: Select Recovery Action
    TUI->>SessionManager: Execute Recovery
    SessionManager->>StepFunctionsClient: Resume/Restart Execution
    StepFunctionsClient-->>SessionManager: Execution Resumed
    SessionManager->>DynamoDBClient: Update Session State
    DynamoDBClient-->>SessionManager: State Updated
```

## 3. Error Handling and Recovery

### 3.1 Error Detection and Analysis

```mermaid
sequenceDiagram
    participant StepFunctionsClient
    participant SessionManager
    participant ErrorHandler
    participant DynamoDBClient
    participant S3Client
    participant NotificationService

    StepFunctionsClient->>SessionManager: Execution Error Event
    SessionManager->>ErrorHandler: Analyze Error
    ErrorHandler->>S3Client: Retrieve Error Logs
    S3Client-->>ErrorHandler: Error Details
    ErrorHandler->>ErrorHandler: Categorize Error
    ErrorHandler->>DynamoDBClient: Store Error Analysis
    DynamoDBClient-->>ErrorHandler: Analysis Stored
    
    alt Recoverable Error
        ErrorHandler->>SessionManager: Retry Strategy
        SessionManager->>StepFunctionsClient: Retry Execution
    else Non-Recoverable Error
        ErrorHandler->>SessionManager: Failure Strategy
        SessionManager->>NotificationService: Send Alert
        NotificationService-->>SessionManager: Alert Sent
    end
```

### 3.2 Automatic Recovery Process

```mermaid
sequenceDiagram
    participant ErrorHandler
    participant SessionManager
    participant StepFunctionsClient
    participant DynamoDBClient
    participant S3Client

    ErrorHandler->>SessionManager: Initiate Recovery
    SessionManager->>DynamoDBClient: Get Last Checkpoint
    DynamoDBClient-->>SessionManager: Checkpoint Data
    SessionManager->>StepFunctionsClient: Resume from Checkpoint
    StepFunctionsClient-->>SessionManager: Execution Resumed
    SessionManager->>DynamoDBClient: Update Session State
    DynamoDBClient-->>SessionManager: State Updated
    SessionManager->>S3Client: Log Recovery Action
    S3Client-->>SessionManager: Recovery Logged
    SessionManager->>ErrorHandler: Recovery Complete
```

## 4. Multi-Session Management

### 4.1 Concurrent Session Handling

```mermaid
sequenceDiagram
    participant User1
    participant User2
    participant TUI1
    participant TUI2
    participant SessionManager
    participant DynamoDBClient
    participant StepFunctionsClient

    User1->>TUI1: Start Pipeline A
    User2->>TUI2: Start Pipeline B
    
    par Parallel Execution
        TUI1->>SessionManager: Create Session A
        SessionManager->>DynamoDBClient: Store Session A
        SessionManager->>StepFunctionsClient: Start Execution A
    and
        TUI2->>SessionManager: Create Session B
        SessionManager->>DynamoDBClient: Store Session B
        SessionManager->>StepFunctionsClient: Start Execution B
    end
    
    SessionManager->>SessionManager: Manage Resource Allocation
    SessionManager->>DynamoDBClient: Update Session States
    DynamoDBClient-->>SessionManager: States Updated
    
    par Status Updates
        SessionManager->>TUI1: Session A Status
        TUI1->>User1: Display Status A
    and
        SessionManager->>TUI2: Session B Status
        TUI2->>User2: Display Status B
    end
```

## 5. Data Flow and Storage

### 5.1 Log Processing and Storage

```mermaid
sequenceDiagram
    participant Operation
    participant Lambda/ECS
    participant S3Client
    participant DynamoDBClient
    participant SessionManager

    Operation->>Lambda/ECS: Execute Task
    Lambda/ECS->>Lambda/ECS: Process Data
    Lambda/ECS->>S3Client: Stream Logs
    S3Client-->>Lambda/ECS: Logs Stored
    Lambda/ECS->>DynamoDBClient: Update Progress
    DynamoDBClient-->>Lambda/ECS: Progress Stored
    Lambda/ECS->>SessionManager: Task Complete
    SessionManager->>SessionManager: Update Session State
```

### 5.2 Report Generation

```mermaid
sequenceDiagram
    participant SessionManager
    participant ReportGenerator
    participant S3Client
    participant DynamoDBClient
    participant TUI

    SessionManager->>ReportGenerator: Generate Report
    ReportGenerator->>DynamoDBClient: Get Session Data
    DynamoDBClient-->>ReportGenerator: Session Metadata
    ReportGenerator->>S3Client: Get Execution Logs
    S3Client-->>ReportGenerator: Log Data
    ReportGenerator->>ReportGenerator: Generate HTML Report
    ReportGenerator->>S3Client: Store Report
    S3Client-->>ReportGenerator: Report Stored
    ReportGenerator->>SessionManager: Report Ready
    SessionManager->>TUI: Show Report URL
```

## 6. Configuration and Deployment

### 6.1 Pipeline Configuration Loading

```mermaid
sequenceDiagram
    participant User
    participant TUI
    participant PipelineManager
    participant S3Client
    participant ConfigValidator

    User->>TUI: Load Pipeline Config
    TUI->>PipelineManager: Load Config Request
    PipelineManager->>S3Client: Retrieve Config File
    S3Client-->>PipelineManager: Config Data
    PipelineManager->>ConfigValidator: Validate Config
    ConfigValidator-->>PipelineManager: Validation Result
    
    alt Valid Configuration
        PipelineManager->>TUI: Config Loaded
        TUI->>User: Show Pipeline Preview
    else Invalid Configuration
        PipelineManager->>TUI: Validation Errors
        TUI->>User: Show Error Messages
    end
```

---

*Document Version: 1.0*  
*Last Updated: 2024-01-XX*  
*Next Review: 2024-XX-XX* 