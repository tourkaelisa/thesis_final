import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { Subscription } from 'rxjs';
import { DataStreamService } from '../../services/data-stream';
import { AuthService } from '../../services/auth';

interface RegPoint { date: string; count: number; cumulative: number; }

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, MatIconModule, MatButtonToggleModule, MatProgressBarModule],
  templateUrl: './dashboard.html',
  styleUrls: ['./dashboard.css']
})
export class Dashboard implements OnInit, OnDestroy {
  private auth = inject(AuthService);
  private streamService = inject(DataStreamService);
  private router = inject(Router);

  stats = signal<any>(null);
  lastUpdated = signal<Date | null>(null);
  private statsSub?: Subscription;

  // ── Registrations chart ──
  chartMode = signal<'cumulative' | 'daily'>('cumulative');
  hoverIndex = signal<number | null>(null);
  readonly geom = { w: 1000, h: 300, mL: 44, mR: 18, mT: 20, mB: 38 };

  // ── Wishlist activity chart ──
  wlMode = signal<'day' | 'week'>('day');
  wlHoverIndex = signal<number | null>(null);
  readonly geomBar = { w: 1000, h: 260, mL: 44, mR: 18, mT: 20, mB: 40 };

  ngOnInit() {
    const user = this.auth.currentUser();
    if (!user) {
      this.router.navigateByUrl('/login');
      return;
    }
    if (user.role !== 2) {
      this.router.navigateByUrl('/');
      return;
    }

    // Το dashboard ενημερώνεται live: ο server ωθεί DASHBOARD_STATS με κάθε
    // μεταβολή των δεδομένων (βλ. realtime hub). Ζητάμε άπαξ τα αρχικά στοιχεία.
    this.statsSub = this.streamService.listenToStore().subscribe(msg => {
      if (msg.type === 'DASHBOARD_STATS') {
        this.stats.set(msg);
        this.lastUpdated.set(new Date());
      }
    });

    this.load();
  }

  ngOnDestroy() {
    this.statsSub?.unsubscribe();
  }

  load() {
    this.streamService.requestDashboardStats();
  }

  maxPopularity(): number {
    const stats = this.stats();
    if (!stats?.top_products?.length) return 1;
    return stats.top_products[0].popularity;
  }

  // ──────────────────────────────────────────────────────────
  //  Registrations timeline chart (custom SVG, no dependencies)
  // ──────────────────────────────────────────────────────────

  /** Σύνοψη περιόδου: σύνολο εγγραφών, καλύτερη ημέρα, τρέχον σύνολο. */
  regSummary = computed(() => {
    const t = this.stats()?.registrations_timeline as RegPoint[] | undefined;
    if (!t?.length) return null;
    const periodTotal = t.reduce((s, d) => s + d.count, 0);
    const peak = t.reduce((m, d) => (d.count > m.count ? d : m), t[0]);
    return {
      periodTotal,
      currentTotal: t[t.length - 1].cumulative,
      peakCount: peak.count,
      peakDate: peak.date,
      days: t.length,
    };
  });

  /** Όλη η γεωμετρία του γραφήματος (σημεία, paths, άξονες) σε συντεταγμένες viewBox. */
  chart = computed(() => {
    const t = this.stats()?.registrations_timeline as RegPoint[] | undefined;
    if (!t?.length) return null;

    const mode = this.chartMode();
    const g = this.geom;
    const innerW = g.w - g.mL - g.mR;
    const innerH = g.h - g.mT - g.mB;
    const n = t.length;
    const values = t.map(d => (mode === 'cumulative' ? d.cumulative : d.count));
    const maxVal = Math.max(1, ...values);

    const xAt = (i: number) => g.mL + (n === 1 ? innerW / 2 : (i / (n - 1)) * innerW);
    const yAt = (v: number) => g.mT + innerH - (v / maxVal) * innerH;

    const points = t.map((d, i) => ({
      x: xAt(i),
      y: yAt(values[i]),
      date: d.date,
      count: d.count,
      cumulative: d.cumulative,
      value: values[i],
    }));

    const line = this.smoothPath(points);
    const baseline = g.mT + innerH;
    const area =
      points.length > 1
        ? `${line} L ${points[n - 1].x},${baseline} L ${points[0].x},${baseline} Z`
        : '';

    // Οριζόντιες γραμμές πλέγματος + ετικέτες τιμών στον άξονα Y
    const ticks = 4;
    const gridlines = [];
    for (let i = 0; i <= ticks; i++) {
      const v = (maxVal / ticks) * i;
      gridlines.push({ y: yAt(v), label: Math.round(v).toString() });
    }

    // Ετικέτες ημερομηνιών (αραιωμένες ώστε να μη στριμώχνονται)
    const step = Math.max(1, Math.ceil(n / 6));
    const xLabels: { x: number; label: string }[] = [];
    for (let i = 0; i < n; i += step) {
      xLabels.push({ x: xAt(i), label: this.shortDate(t[i].date) });
    }
    if (xLabels[xLabels.length - 1]?.x !== points[n - 1].x) {
      xLabels.push({ x: points[n - 1].x, label: this.shortDate(t[n - 1].date) });
    }

    const hitW = points.length > 1 ? points[1].x - points[0].x : innerW;

    return { points, line, area, gridlines, xLabels, baseline, maxVal, innerH, hitW };
  });

  /** Το ενεργό σημείο hover (ή το τελευταίο σημείο ως προεπιλογή). */
  activePoint = computed(() => {
    const c = this.chart();
    if (!c) return null;
    const idx = this.hoverIndex();
    return idx != null ? c.points[idx] : null;
  });

  setMode(mode: 'cumulative' | 'daily') {
    if (mode) this.chartMode.set(mode);
  }

  /**
   * Monotone cubic Hermite (Fritsch–Carlson) → cubic Bézier.
   * Σε αντίθεση με το Catmull-Rom, η καμπύλη δεν κάνει overshoot: μένει εντός
   * του εύρους των δεδομένων ανάμεσα στα σημεία, οπότε ΠΟΤΕ δεν πέφτει κάτω
   * από το 0 (οι εγγραφές δεν μπορούν να είναι αρνητικές).
   */
  private smoothPath(pts: { x: number; y: number }[]): string {
    const n = pts.length;
    if (!n) return '';
    if (n === 1) return `M ${pts[0].x},${pts[0].y}`;
    if (n === 2) return `M ${pts[0].x},${pts[0].y} L ${pts[1].x},${pts[1].y}`;

    // Κλίσεις των τμημάτων (secants)
    const dx: number[] = [];
    const delta: number[] = [];
    for (let i = 0; i < n - 1; i++) {
      dx[i] = pts[i + 1].x - pts[i].x;
      delta[i] = (pts[i + 1].y - pts[i].y) / dx[i];
    }

    // Εφαπτομένες σε κάθε σημείο
    const m: number[] = new Array(n);
    m[0] = delta[0];
    m[n - 1] = delta[n - 2];
    for (let i = 1; i < n - 1; i++) {
      // Σε τοπικό ακρότατο (αλλαγή προσήμου) η κλίση μηδενίζεται → καμία υπέρβαση
      m[i] = delta[i - 1] * delta[i] <= 0 ? 0 : (delta[i - 1] + delta[i]) / 2;
    }

    // Διόρθωση Fritsch–Carlson ώστε κάθε τμήμα να παραμένει μονότονο
    for (let i = 0; i < n - 1; i++) {
      if (delta[i] === 0) {
        m[i] = 0;
        m[i + 1] = 0;
        continue;
      }
      const a = m[i] / delta[i];
      const b = m[i + 1] / delta[i];
      const s = a * a + b * b;
      if (s > 9) {
        const tau = 3 / Math.sqrt(s);
        m[i] = tau * a * delta[i];
        m[i + 1] = tau * b * delta[i];
      }
    }

    // Hermite → cubic Bézier ανά τμήμα
    let d = `M ${pts[0].x},${pts[0].y}`;
    for (let i = 0; i < n - 1; i++) {
      const cp1x = pts[i].x + dx[i] / 3;
      const cp1y = pts[i].y + (m[i] * dx[i]) / 3;
      const cp2x = pts[i + 1].x - dx[i] / 3;
      const cp2y = pts[i + 1].y - (m[i + 1] * dx[i]) / 3;
      d += ` C ${cp1x},${cp1y} ${cp2x},${cp2y} ${pts[i + 1].x},${pts[i + 1].y}`;
    }
    return d;
  }

  /** "2026-06-12" → "12/6" */
  shortDate(iso: string): string {
    const [, m, d] = iso.split('-');
    return `${parseInt(d, 10)}/${parseInt(m, 10)}`;
  }

  /** "2026-06-12" → "12 Ιουν" για το tooltip. */
  prettyDate(iso: string): string {
    const months = ['Ιαν', 'Φεβ', 'Μαρ', 'Απρ', 'Μαϊ', 'Ιουν', 'Ιουλ', 'Αυγ', 'Σεπ', 'Οκτ', 'Νοε', 'Δεκ'];
    const [, m, d] = iso.split('-');
    return `${parseInt(d, 10)} ${months[parseInt(m, 10) - 1]}`;
  }

  /** Μετατροπή συντεταγμένης viewBox σε ποσοστό (για το HTML tooltip). */
  pctX(x: number): number { return (x / this.geom.w) * 100; }
  pctY(y: number): number { return (y / this.geom.h) * 100; }

  // ──────────────────────────────────────────────────────────
  //  Wishlist activity chart (custom SVG bars, no dependencies)
  // ──────────────────────────────────────────────────────────

  /** Οι «κάδοι» δεδομένων: ανά ημέρα ή αθροισμένοι ανά εβδομάδα. */
  private wlBuckets = computed(() => {
    const raw = this.stats()?.wishlist_activity as { date: string; count: number }[] | undefined;
    if (!raw?.length) return null;
    if (this.wlMode() === 'week') return this.toWeekly(raw);
    return raw.map(d => ({ label: this.shortDate(d.date), tip: this.prettyDate(d.date), count: d.count }));
  });

  /** Σύνοψη: σύνολο προσθηκών, ημέρα κορύφωσης, μέσος όρος/ημέρα. */
  wlSummary = computed(() => {
    const raw = this.stats()?.wishlist_activity as { date: string; count: number }[] | undefined;
    if (!raw?.length) return null;
    const total = raw.reduce((s, d) => s + d.count, 0);
    const peak = raw.reduce((m, d) => (d.count > m.count ? d : m), raw[0]);
    return {
      total,
      peakCount: peak.count,
      peakDate: peak.date,
      avg: total / raw.length,
      days: raw.length,
    };
  });

  /** Γεωμετρία των μπαρών (συντεταγμένες viewBox). */
  wlChart = computed(() => {
    const buckets = this.wlBuckets();
    if (!buckets?.length) return null;

    const g = this.geomBar;
    const innerW = g.w - g.mL - g.mR;
    const innerH = g.h - g.mT - g.mB;
    const n = buckets.length;
    const maxVal = Math.max(1, ...buckets.map(b => b.count));
    const slot = innerW / n;
    const barW = Math.min(slot * 0.6, 44);
    const baseline = g.mT + innerH;

    const bars = buckets.map((b, i) => {
      const h = (b.count / maxVal) * innerH;
      const slotX = g.mL + slot * i;
      return {
        x: slotX + (slot - barW) / 2,
        y: baseline - h,
        w: barW,
        h,
        cx: slotX + slot / 2,
        count: b.count,
        label: b.label,
        tip: b.tip,
      };
    });

    const ticks = 4;
    const gridlines = [];
    for (let i = 0; i <= ticks; i++) {
      const v = (maxVal / ticks) * i;
      gridlines.push({ y: baseline - (v / maxVal) * innerH, label: Math.round(v).toString() });
    }

    // ετικέτες X: όλες στην εβδομαδιαία όψη, αραιωμένες στην ημερήσια
    const labelEvery = this.wlMode() === 'week' ? 1 : Math.ceil(n / 8);

    return { bars, gridlines, baseline, innerH, maxVal, labelEvery, hitW: slot, mT: g.mT };
  });

  /** Η μπάρα κάτω από τον δείκτη (για tooltip). */
  wlActive = computed(() => {
    const c = this.wlChart();
    if (!c) return null;
    const i = this.wlHoverIndex();
    return i != null ? c.bars[i] : null;
  });

  setWlMode(mode: 'day' | 'week') {
    if (mode) this.wlMode.set(mode);
  }

  /** Άθροιση των ημερήσιων τιμών σε εβδομαδιαίους κάδους (7άδες). */
  private toWeekly(raw: { date: string; count: number }[]) {
    const out: { label: string; tip: string; count: number }[] = [];
    for (let i = 0; i < raw.length; i += 7) {
      const chunk = raw.slice(i, i + 7);
      const start = chunk[0].date;
      const end = chunk[chunk.length - 1].date;
      out.push({
        label: this.shortDate(start),
        tip: `${this.prettyDate(start)} – ${this.prettyDate(end)}`,
        count: chunk.reduce((s, d) => s + d.count, 0),
      });
    }
    return out;
  }

  pctBarX(x: number): number { return (x / this.geomBar.w) * 100; }
  pctBarY(y: number): number { return (y / this.geomBar.h) * 100; }

  // ──────────────────────────────────────────────────────────
  //  Engagement / ενεργοί χρήστες (donut + κατανομή)
  // ──────────────────────────────────────────────────────────

  engagement = computed(() => this.stats()?.engagement ?? null);

  /** Γεωμετρία του donut (τόξο ενεργών χρηστών). */
  donut = computed(() => {
    const e = this.engagement();
    if (!e || !e.total_users) return null;
    const r = 70;
    const c = 2 * Math.PI * r;
    const frac = e.active_users / e.total_users;
    const dash = frac * c;
    return { r, c, dash, offset: c - dash, cx: 90, cy: 90 };
  });

  /** Κατανομή μεγέθους λίστας, κανονικοποιημένη ως προς τον μεγαλύτερο κάδο. */
  distRows = computed(() => {
    const dist = this.engagement()?.distribution as { label: string; count: number }[] | undefined;
    if (!dist?.length) return [];
    const max = Math.max(1, ...dist.map(d => d.count));
    return dist.map(d => ({ ...d, pct: (d.count / max) * 100 }));
  });

  // ──────────────────────────────────────────────────────────
  //  Προϊόντα που εγκαταλείπονται (churn)
  // ──────────────────────────────────────────────────────────

  abandoned = computed(() => (this.stats()?.abandoned_products ?? []) as any[]);

  /** Μέγιστες συνολικές προσθήκες — για κανονικοποίηση του μήκους των μπαρών. */
  maxAbandonAdditions = computed(() => {
    const a = this.abandoned();
    return a.length ? Math.max(...a.map(p => p.additions)) : 1;
  });
}
