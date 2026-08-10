use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use rusqlite::Connection;
use serde::{Deserialize, Serialize};
use chrono::{TimeZone, Utc};
use axum::{
    extract::{Query, State},
    http::StatusCode,
    response::IntoResponse,
    routing::{get, post},
    Json, Router,
};

#[derive(Serialize, Deserialize, Debug, Clone)]
struct DxyRecord {
    time: String,
    open: f64,
    high: f64,
    low: f64,
    close: f64,
    tick_volume: i64,
    spread: i32,
    real_volume: i64,
}

#[derive(Deserialize, Debug)]
struct YahooChartResponse {
    chart: YahooChartData,
}

#[derive(Deserialize, Debug)]
struct YahooChartData {
    result: Option<Vec<YahooResultItem>>,
    #[allow(dead_code)]
    error: Option<serde_json::Value>,
}

#[derive(Deserialize, Debug)]
struct YahooResultItem {
    timestamp: Option<Vec<i64>>,
    indicators: YahooIndicators,
}

#[derive(Deserialize, Debug)]
struct YahooIndicators {
    quote: Vec<YahooQuote>,
}

#[derive(Deserialize, Debug)]
struct YahooQuote {
    open: Option<Vec<Option<f64>>>,
    high: Option<Vec<Option<f64>>>,
    low: Option<Vec<Option<f64>>>,
    close: Option<Vec<Option<f64>>>,
    volume: Option<Vec<Option<f64>>>,
}

struct AppState {
    db_path: PathBuf,
}

#[derive(Deserialize)]
struct HistoricalParams {
    limit: Option<usize>,
}

fn get_db_path() -> PathBuf {
    if Path::new("data/database").is_dir() {
        PathBuf::from("data/database/dxy_data.sqlite")
    } else if Path::new("../data/database").is_dir() {
        PathBuf::from("../data/database/dxy_data.sqlite")
    } else {
        let _ = fs::create_dir_all("data/database");
        PathBuf::from("data/database/dxy_data.sqlite")
    }
}

fn init_db(db_path: &Path) -> Result<(), rusqlite::Error> {
    let conn = Connection::open(db_path)?;
    
    conn.execute(
        "CREATE TABLE IF NOT EXISTS DXY_H1 (
            time TEXT PRIMARY KEY,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            tick_volume INTEGER,
            spread INTEGER,
            real_volume INTEGER
        )",
        [],
    )?;
    
    conn.execute(
        "CREATE TABLE IF NOT EXISTS DXY_16385 (
            time TEXT PRIMARY KEY,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            tick_volume INTEGER,
            spread INTEGER,
            real_volume INTEGER
        )",
        [],
    )?;
    
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_DXY_H1_time ON DXY_H1 (time)", [])?;
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_DXY_16385_time ON DXY_16385 (time)", [])?;
    
    Ok(())
}

async fn harvest_dxy(db_path: &Path) -> Result<usize, Box<dyn std::error::Error + Send + Sync>> {
    let ticker = "DX-Y.NYB";
    let url = format!(
        "https://query1.finance.yahoo.com/v8/finance/chart/{}?range=730d&interval=1h",
        ticker
    );
    
    let client = reqwest::Client::builder()
        .danger_accept_invalid_certs(true)
        .user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        .build()?;
        
    let res = client.get(&url).send().await?;
    if !res.status().is_success() {
        return Err(format!("Failed to fetch DXY: HTTP status {}", res.status()).into());
    }
    
    let response_data: YahooChartResponse = res.json().await?;
    let result_items = response_data.chart.result.ok_or("No result items in response")?;
    if result_items.is_empty() {
        return Err("Result items empty".into());
    }
    
    let item = &result_items[0];
    let timestamps = item.timestamp.as_ref().ok_or("No timestamps in result")?;
    let quotes = &item.indicators.quote;
    if quotes.is_empty() {
        return Err("No quotes in indicators".into());
    }
    let quote = &quotes[0];
    
    let opens = quote.open.as_ref().ok_or("No open prices")?;
    let highs = quote.high.as_ref().ok_or("No high prices")?;
    let lows = quote.low.as_ref().ok_or("No low prices")?;
    let closes = quote.close.as_ref().ok_or("No close prices")?;
    let volumes = quote.volume.as_ref().ok_or("No volumes")?;
    
    let len = timestamps.len();
    if opens.len() < len || highs.len() < len || lows.len() < len || closes.len() < len || volumes.len() < len {
        return Err("Quote vectors length mismatch".into());
    }
    
    let mut conn = Connection::open(db_path)?;
    let tx = conn.transaction()?;
    let mut inserted_count = 0;
    
    {
        let mut stmt_h1 = tx.prepare(
            "INSERT OR IGNORE INTO DXY_H1 (time, open, high, low, close, tick_volume, spread, real_volume) 
             VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        )?;
        
        let mut stmt_16385 = tx.prepare(
            "INSERT OR IGNORE INTO DXY_16385 (time, open, high, low, close, tick_volume, spread, real_volume) 
             VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        )?;
        
        for i in 0..len {
            let ts = timestamps[i];
            
            let open = match opens[i] { Some(val) => val, None => continue };
            let high = match highs[i] { Some(val) => val, None => continue };
            let low = match lows[i] { Some(val) => val, None => continue };
            let close = match closes[i] { Some(val) => val, None => continue };
            let vol = match volumes[i] { Some(val) => val as i64, None => 0 };
            
            let datetime = Utc.timestamp_opt(ts, 0).single().ok_or("Invalid timestamp")?;
            let formatted_time = datetime.format("%Y-%m-%d %H:%M:%S+00:00").to_string();
            
            let r1 = stmt_h1.execute(rusqlite::params![
                formatted_time, open, high, low, close, vol, 0, 0
            ])?;
            
            let r2 = stmt_16385.execute(rusqlite::params![
                formatted_time, open, high, low, close, vol, 0, 0
            ])?;
            
            if r1 > 0 || r2 > 0 {
                inserted_count += 1;
            }
        }
    }
    
    tx.commit()?;
    Ok(inserted_count)
}

fn spawn_periodic_harvest(db_path: PathBuf) {
    tokio::spawn(async move {
        println!("Starting periodic DXY harvest task (every 20 minutes)...");
        loop {
            tokio::time::sleep(tokio::time::Duration::from_secs(20 * 60)).await;
            println!("Periodic check: harvesting DXY data...");
            match harvest_dxy(&db_path).await {
                Ok(count) => println!("Periodic harvest complete: Inserted {} new rows", count),
                Err(e) => eprintln!("Periodic harvest error: {}", e),
            }
        }
    });
}

async fn get_latest(State(state): State<Arc<AppState>>) -> impl IntoResponse {
    let conn = match Connection::open(&state.db_path) {
        Ok(c) => c,
        Err(e) => return (StatusCode::INTERNAL_SERVER_ERROR, Json(serde_json::json!({ "error": e.to_string() }))).into_response(),
    };
    
    let mut stmt = match conn.prepare(
        "SELECT time, open, high, low, close, tick_volume, spread, real_volume 
         FROM DXY_H1 ORDER BY time DESC LIMIT 1"
    ) {
        Ok(s) => s,
        Err(e) => return (StatusCode::INTERNAL_SERVER_ERROR, Json(serde_json::json!({ "error": e.to_string() }))).into_response(),
    };
    
    let record_res = stmt.query_row([], |row| {
        Ok(DxyRecord {
            time: row.get(0)?,
            open: row.get(1)?,
            high: row.get(2)?,
            low: row.get(3)?,
            close: row.get(4)?,
            tick_volume: row.get(5)?,
            spread: row.get(6)?,
            real_volume: row.get(7)?,
        })
    });
    
    match record_res {
        Ok(record) => (StatusCode::OK, Json(record)).into_response(),
        Err(rusqlite::Error::QueryReturnedNoRows) => (StatusCode::NOT_FOUND, Json(serde_json::json!({ "error": "No records found" }))).into_response(),
        Err(e) => (StatusCode::INTERNAL_SERVER_ERROR, Json(serde_json::json!({ "error": e.to_string() }))).into_response(),
    }
}

async fn get_historical(
    State(state): State<Arc<AppState>>,
    Query(params): Query<HistoricalParams>,
) -> impl IntoResponse {
    let limit = params.limit.unwrap_or(1000);
    
    let conn = match Connection::open(&state.db_path) {
        Ok(c) => c,
        Err(e) => return (StatusCode::INTERNAL_SERVER_ERROR, Json(serde_json::json!({ "error": e.to_string() }))).into_response(),
    };
    
    let mut stmt = match conn.prepare(
        "SELECT time, open, high, low, close, tick_volume, spread, real_volume 
         FROM DXY_H1 ORDER BY time DESC LIMIT ?"
    ) {
        Ok(s) => s,
        Err(e) => return (StatusCode::INTERNAL_SERVER_ERROR, Json(serde_json::json!({ "error": e.to_string() }))).into_response(),
    };
    
    let records_iter = match stmt.query_map([limit], |row| {
        Ok(DxyRecord {
            time: row.get(0)?,
            open: row.get(1)?,
            high: row.get(2)?,
            low: row.get(3)?,
            close: row.get(4)?,
            tick_volume: row.get(5)?,
            spread: row.get(6)?,
            real_volume: row.get(7)?,
        })
    }) {
        Ok(iter) => iter,
        Err(e) => return (StatusCode::INTERNAL_SERVER_ERROR, Json(serde_json::json!({ "error": e.to_string() }))).into_response(),
    };
    
    let mut records = Vec::new();
    for rec in records_iter {
        if let Ok(r) = rec {
            records.push(r);
        }
    }
    
    // Reverse records to be chronological (oldest to newest) to match MT5 client rates
    records.reverse();
    
    (StatusCode::OK, Json(records)).into_response()
}

async fn trigger_harvest(State(state): State<Arc<AppState>>) -> impl IntoResponse {
    match harvest_dxy(&state.db_path).await {
        Ok(count) => (StatusCode::OK, Json(serde_json::json!({ "status": "success", "inserted": count }))).into_response(),
        Err(e) => (StatusCode::INTERNAL_SERVER_ERROR, Json(serde_json::json!({ "error": e.to_string() }))).into_response(),
    }
}

#[tokio::main]
async fn main() {
    let db_path = get_db_path();
    println!("Database path: {:?}", db_path);
    
    if let Err(e) = init_db(&db_path) {
        eprintln!("Database initialization failed: {}", e);
        std::process::exit(1);
    }
    
    // Run an initial harvest asynchronously in the background so server starts immediately
    let startup_path = db_path.clone();
    tokio::spawn(async move {
        println!("Performing initial DXY harvest on startup...");
        match harvest_dxy(&startup_path).await {
            Ok(count) => println!("Initial harvest complete: Inserted {} new rows", count),
            Err(e) => eprintln!("Initial harvest error: {}", e),
        }
    });
    
    // Start periodic background loop
    spawn_periodic_harvest(db_path.clone());
    
    let app_state = Arc::new(AppState { db_path });
    
    let app = Router::new()
        .route("/api/dxy/latest", get(get_latest))
        .route("/api/dxy/historical", get(get_historical))
        .route("/api/dxy/harvest", post(trigger_harvest))
        .layer(tower_http::cors::CorsLayer::permissive())
        .with_state(app_state);
        
    let listener = match tokio::net::TcpListener::bind("127.0.0.1:8081").await {
        Ok(l) => l,
        Err(e) => {
            eprintln!("Failed to bind port 8081: {}", e);
            std::process::exit(1);
        }
    };
    
    println!("DXY Rust Service listening on http://127.0.0.1:8081");
    if let Err(e) = axum::serve(listener, app).await {
        eprintln!("Server error: {}", e);
    }
}
