import {
  AreaSeries,
  BarSeries,
  BaselineSeries,
  CandlestickSeries,
  createChart,
  HistogramSeries,
  LineSeries,
  LineStyle,
} from 'lightweight-charts';

export class ChartManager {
  constructor(options = {}) {
    this.chart = null;
    this.series = new Map();
    this.container = null;
    this.loadedBars = 500;

    this.defaultOptions = {
      layout: {
        textColor: '#d1d4dc',
        background: { type: 'solid', color: 'transparent' },
        panes: {
          separatorColor: 'rgba(96,96,96,0.3)',
        },
      },
      grid: {
        vertLines: { color: 'transparent' },
        horzLines: { color: 'transparent' },
      },
      autoSize: true,
      ...options,
    };

    this.timeScaleOptions = {
      timeVisible: true,
      secondsVisible: false,
    };

    this.seriesTypes = {
      line: LineSeries,
      area: AreaSeries,
      bar: BarSeries,
      baseline: BaselineSeries,
      candlestick: CandlestickSeries,
      histogram: HistogramSeries,
    };
  }

  // Convert chart time to x pixel coordinate
  xFromTime(t) {
    try {
      const x = this.chart?.timeScale()?.timeToCoordinate(t);
      return x == null ? null : x;
    } catch { return null; }
  }

  // Convert price to y pixel coordinate (using main series scale)
  yFromPrice(p) {
    const s = this.getMainSeries();
    try {
      const y = s?.priceScale()?.priceToCoordinate(p);
      return y == null ? null : y;
    } catch { return null; }
  }

  init(containerElement) {
    this.container = containerElement;

    try {
      this.chart = createChart(containerElement, this.defaultOptions);
      this.chart.timeScale().applyOptions(this.timeScaleOptions);
    } catch (error) {
      console.error('Failed to initialize chart:', error);
    }
  }

  // Toggle grid on/off
  setGrid(on = false) {
    if (!this.chart) return;
    const gridOpts = on
      ? { vertLines: { color: 'rgba(70, 70, 70, 0.5)' }, horzLines: { color: 'rgba(70, 70, 70, 0.5)' } }
      : { vertLines: { color: 'transparent' }, horzLines: { color: 'transparent' } };
    try {
      this.chart.applyOptions({ grid: gridOpts });
    } catch (e) {
      // noop
    }
  }

  // Trendline helpers using simple 2-point line series in main pane (paneIndex 0)
  addTrendline(id, a, b, options = {}) {
    const key = `tl_${id}`;
    const data = [
      { time: a.time, value: a.price },
      { time: b.time, value: b.price },
    ];
    const seriesOptions = { 
      lineWidth: 2, 
      color: '#ffffff', 
      lineStyle: 0, // 0 = Solid (using numeric value instead of enum)
      lineType: 0, // Simple line (not stepped)
      lastValueVisible: false, // Hide value labels
      ...options 
    };
    return this.addSeries(key, 'line', data, seriesOptions, 0);
  }

  updateTrendline(id, a, b) {
    const key = `tl_${id}`;
    const info = this.series.get(key);
    if (!info) return false;
    const data = [
      { time: a.time, value: a.price },
      { time: b.time, value: b.price },
    ];
    try {
      info.series.setData(data);
      info.data = data;
      return true;
    } catch (e) {
      return false;
    }
  }

  removeTrendline(id) {
    const key = `tl_${id}`;
    if (this.series.has(key)) {
      this.removeSeries(key);
    }
  }

  // Click subscriptions for drawing tools
  subscribeClick(callback) {
    if (this.chart) {
      this.chart.subscribeClick(callback);
    }
  }

  setCrosshairEnabled(enabled) {
    if (this.chart) {
      this.chart.applyOptions({ crosshair: { vertLine: { visible: enabled }, horzLine: { visible: enabled } } });
    }
  }

  unsubscribeClick(callback) {
    if (this.chart) {
      this.chart.unsubscribeClick(callback);
    }
  }

  getMainSeries() {
    return this.series.get('ohlc')?.series || null;
  }

  priceFromY(y) {
    const s = this.getMainSeries();
    try {
      // Try different methods based on lightweight-charts version
      let price = null;
      
      // Method 1: Try coordinateToPrice on price scale
      if (s?.priceScale()?.coordinateToPrice) {
        price = s.priceScale().coordinateToPrice(y);
      }
      
      // Method 2: Try coordinateToPrice on series (newer versions)
      if (!price && s?.coordinateToPrice) {
        price = s.coordinateToPrice(y);
      }
      
      // Method 3: Use the chart's price scale API
      if (!price && this.chart) {
        const priceScale = this.chart.priceScale('right');
        if (priceScale?.coordinateToPrice) {
          price = priceScale.coordinateToPrice(y);
        }
      }
      
      return price;
    } catch (e) {
      return null;
    }
  }

  // Convert an x pixel coordinate to chart time (UTCTimestamp seconds)
  timeFromX(x) {
    try {
      const t = this.chart?.timeScale()?.coordinateToTime(x);
      if (t == null) return null;
      if (typeof t === 'number') return t; // UTCTimestamp seconds
      // BusinessDay object { year, month, day }
      if (typeof t === 'object' && t.year && t.month && t.day) {
        const secs = Date.UTC(t.year, (t.month - 1), t.day) / 1000;
        return Math.floor(secs);
      }
      return null;
    } catch {
      return null;
    }
  }

  addSeries(key, type, data, seriesOptions = {}, paneIndex = 0) {
    if (!this.chart) {
      console.error('Chart not initialized');
      return null;
    }

    if (this.series.has(key)) {
      this.removeSeries(key);
    }

    const newSeries = this.createSeries(type, seriesOptions, paneIndex);

    if (newSeries) {
      newSeries.setData(data);
      this.series.set(key, {
        series: newSeries,
        type,
        data: [...data],
        options: { ...seriesOptions },
      });
    }

    return newSeries;
  }

  createSeries(type, seriesOptions = {}, paneIndex) {
    if (!this.chart) {
      console.error('Chart not initialized');
      return null;
    }

    const SeriesConstructor = this.seriesTypes[type];
    if (!SeriesConstructor) {
      console.error('Invalid series type:', type);
      return null;
    }

    try {
      const newSeries = this.chart.addSeries(SeriesConstructor, seriesOptions, paneIndex);
      return newSeries;
    } catch (error) {
      console.error('Failed to create series:', error);
      return null;
    }
  }

  removeSeries(key) {
    const seriesInfo = this.series.get(key);
    if (!seriesInfo || !seriesInfo.series) {
      // Already removed or never existed; safe no-op
      this.series.delete(key);
      return;
    }

    try {
      this.chart.removeSeries(seriesInfo.series);
      this.series.delete(key);
    } catch (error) {
      console.error(`Failed to remove series '${key}':`, error);
    }
  }

  updateSeriesOptions(key, newOptions) {
    const seriesInfo = this.series.get(key);
    if (!seriesInfo) {
      console.error(`Series '${key}' not found`);
      return false;
    }

    try {
      seriesInfo.series.applyOptions(newOptions);
      seriesInfo.options = { ...seriesInfo.options, ...newOptions };
      return true;
    } catch (error) {
      console.error(`Failed to update options for series '${key}':`, error);
      return false;
    }
  }

  async getPaneHtmlElement(paneIndex = 0) {
    if (!this.isValidPaneIndex(paneIndex)) {
      return null;
    }

    const pane = this.chart.panes()[paneIndex];
    return await this.waitForPaneHtmlElement(pane);
  }

  isValidPaneIndex(paneIndex) {
    const panes = this.chart.panes();
    const isValid = paneIndex >= 0 && paneIndex < panes.length;

    if (!isValid) {
      console.error(`Invalid pane index: ${paneIndex}. Available panes: ${panes.length}`);
    }

    return isValid;
  }

  async waitForPaneHtmlElement(pane, maxAttempts = 10, delay = 100) {
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      const element = this.tryGetHtmlElement(pane);
      if (element) {
        return element;
      }

      if (attempt < maxAttempts - 1) {
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }

    console.warn('Pane HTML element not available after maximum attempts');
    return null;
  }

  tryGetHtmlElement(pane) {
    try {
      return pane?.getHTMLElement?.() || null;
    } catch {
      return null;
    }
  }

  subscribeCrosshairMove(callback) {
    if (this.chart) {
      this.chart.subscribeCrosshairMove(callback);
    }
  }

  subscribeVisibleLogicalRangeChange(callback) {
    if (this.chart) {
      this.chart.timeScale().subscribeVisibleLogicalRangeChange(callback);
    }
  }

  destroy() {
    if (this.chart) {
      this.series.forEach((_, key) => {
        this.removeSeries(key);
      });

      this.chart.remove();
      this.chart = null;
      this.container = null;
    }
  }
}

// Extra helpers on prototype for zoom/scroll
ChartManager.prototype.getLogicalRange = function () {
  try { return this.chart?.timeScale()?.getVisibleLogicalRange?.() || null; } catch { return null; }
};
ChartManager.prototype.setLogicalRange = function (range) {
  try { this.chart?.timeScale()?.setVisibleLogicalRange?.(range); } catch {}
};
ChartManager.prototype.zoom = function (factor = 1.2) {
  const r = this.getLogicalRange();
  if (!r) return;
  const center = (r.from + r.to) / 2;
  const half = (r.to - r.from) / 2;
  const newHalf = half / factor;
  this.setLogicalRange({ from: center - newHalf, to: center + newHalf });
};
ChartManager.prototype.zoomIn = function () { this.zoom(1.4); };
ChartManager.prototype.zoomOut = function () { this.zoom(1 / 1.4); };
ChartManager.prototype.resetZoom = function () {
  try { this.chart?.timeScale()?.fitContent?.(); } catch {}
};
ChartManager.prototype.scrollBars = function (delta = 10) {
  try {
    const ts = this.chart?.timeScale?.();
    const range = ts?.getVisibleLogicalRange?.();
    if (!range) return;
    const width = (range.to - range.from);
    const shift = width * (delta / 50);
    this.setLogicalRange({ from: range.from + shift, to: range.to + shift });
  } catch {}
};
