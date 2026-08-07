import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { switchMap } from 'rxjs/operators';
import { ApiService, ApiPatient, ImageAnalysisResult, ClinicalSummaryResult } from '../../services/api.service';
import { AuthService } from '../../services/auth.service';

interface Vitals { bp: string; pulse: string; temp: string; spo2: string; weight: string; height: string; }
export interface ImageItem { name: string; url: string; annotated?: boolean; }

@Component({
  selector: 'app-consultation',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './consultation.component.html',
  styleUrl: './consultation.component.scss'
})
export class ConsultationComponent implements OnInit {
  patient: ApiPatient | null = null;
  isLoading = true;
  isSaving = false;
  isCompleting = false;
  savedDraft = false;
  draftError = '';

  // Validation (symptoms + vitals are mandatory to complete a consultation)
  showErrors = false;
  formError  = '';

  activeTab: 'clinical' | 'images' = 'clinical';

  symptoms: string[] = [];
  symptomInput = '';
  vitals: Vitals = { bp: '', pulse: '', temp: '', spo2: '', weight: '', height: '' };
  diagnosis = '';
  notes = '';

  uploadedImages: ImageItem[] = [];
  isDragOver  = false;
  uploadError = '';
  private readonly MAX_IMAGE_BYTES = 20 * 1024 * 1024;
  private readonly ACCEPTED_TYPES  = ['image/png', 'image/jpeg'];
  jrNotes = '';  // Jr. doctor's past medication / history notes (preserved across save)

  // ── Annotation state ─────────────────────────────────
  annotating: { img: ImageItem; idx: number } | null = null;
  annotTool: 'pencil' | 'eraser' | 'text' = 'pencil';
  annotColor = '#ef4444';
  annotSize = 4;
  annotIsDrawing = false;
  textInputActive = false;
  textX = 0;
  textY = 0;
  textValue = '';
  undoStack: ImageData[] = [];

  readonly ANNOT_COLORS = ['#ef4444','#f97316','#eab308','#22c55e','#3b82f6','#8b5cf6','#000000','#ffffff'];

  private drawCtx: CanvasRenderingContext2D | null = null;
  private drawCanvas: HTMLCanvasElement | null = null;
  private annotLastX = 0;
  private annotLastY = 0;

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private api: ApiService,
    public auth: AuthService
  ) {}

  ngOnInit() {
    const id = Number(this.route.snapshot.paramMap.get('id'));
    this.api.getPatient(id).subscribe({
      next: (p) => { this.patient = p; this.loadExistingData(p); this.isLoading = false; },
      error: () => { this.isLoading = false; this.router.navigate(['/doctor-queue']); }
    });
  }

  private loadExistingData(p: ApiPatient) {
    if (!p.medicalHistory) return;
    try {
      const d = JSON.parse(p.medicalHistory);
      if (d.symptoms)        this.symptoms        = d.symptoms;
      if (d.vitals)          this.vitals          = { ...this.vitals, ...d.vitals };
      if (d.diagnosis)       this.diagnosis       = d.diagnosis;
      if (d.notes)           this.notes           = d.notes;
      if (d.images?.length)  this.uploadedImages  = d.images;
      if (d.jrNotes)         this.jrNotes         = d.jrNotes;
    } catch {
      // Not JSON — this is the jr. doctor's plain-text past medication / history notes
      this.jrNotes = p.medicalHistory;
    }
  }

  addSymptom() {
    const s = this.symptomInput.trim();
    if (s && !this.symptoms.includes(s)) this.symptoms.push(s);
    this.symptomInput = '';
    this.onFieldEdit();
  }

  // ── Mandatory-field validation ─────────────────────────
  private isVitalsComplete(): boolean {
    const v = this.vitals;
    return !!(v.bp.trim() && v.pulse.trim() && v.temp.trim() && v.spo2.trim() && v.weight.trim() && v.height.trim());
  }

  get symptomsInvalid(): boolean { return this.showErrors && this.symptoms.length === 0; }
  get vitalsInvalid(): boolean { return this.showErrors && !this.isVitalsComplete(); }

  isVitalMissing(field: keyof Vitals): boolean {
    return this.showErrors && !this.vitals[field].trim();
  }

  onFieldEdit() {
    if (this.formError && this.symptoms.length && this.isVitalsComplete()) this.formError = '';
  }

  private validateClinical(): boolean {
    this.showErrors = true;
    const okSymptoms = this.symptoms.length > 0;
    const okVitals   = this.isVitalsComplete();
    if (okSymptoms && okVitals) { this.formError = ''; return true; }
    this.activeTab = 'clinical';   // bring the doctor back to the fields that need attention
    this.formError =
      !okSymptoms && !okVitals ? 'Please add at least one symptom and complete all vitals before finishing.'
      : !okSymptoms            ? 'Please add at least one presenting symptom.'
      :                          'Please complete all vital fields before finishing.';
    return false;
  }

  onSymptomKey(e: KeyboardEvent) {
    if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); this.addSymptom(); }
    else if (e.key === 'Backspace' && !this.symptomInput && this.symptoms.length) this.symptoms.pop();
  }

  removeSymptom(i: number) { this.symptoms.splice(i, 1); }

  get allergyList(): string[] {
    return this.patient?.allergies?.split(',').map(s => s.trim()).filter(Boolean) ?? [];
  }

  goToImages() { this.activeTab = 'images'; }

  onFileSelect(e: Event) {
    const input = e.target as HTMLInputElement;
    this.addFiles(input.files);
    input.value = '';   // allow re-selecting the same file
  }

  onDragOver(e: DragEvent) { e.preventDefault(); this.isDragOver = true; }

  onDragLeave(e: DragEvent) { e.preventDefault(); this.isDragOver = false; }

  onDrop(e: DragEvent) {
    e.preventDefault();
    this.isDragOver = false;
    this.addFiles(e.dataTransfer?.files ?? null);
  }

  private addFiles(files: FileList | null) {
    if (!files?.length) return;
    this.uploadError = '';
    const rejected: string[] = [];

    for (const f of Array.from(files)) {
      if (!this.ACCEPTED_TYPES.includes(f.type)) { rejected.push(`${f.name} (not a PNG/JPG)`); continue; }
      if (f.size > this.MAX_IMAGE_BYTES)         { rejected.push(`${f.name} (over 20MB)`);     continue; }

      const reader = new FileReader();
      reader.onload  = ev => { this.uploadedImages.push({ name: this.uniqueName(f.name), url: ev.target!.result as string }); };
      reader.onerror = ()  => { this.uploadError = `Could not read ${f.name}.`; };
      reader.readAsDataURL(f);
    }

    if (rejected.length) this.uploadError = `Skipped: ${rejected.join(', ')}.`;
  }

  /** The image grid tracks by name, so duplicates must be disambiguated. */
  private uniqueName(name: string): string {
    if (!this.uploadedImages.some(i => i.name === name)) return name;
    const dot  = name.lastIndexOf('.');
    const base = dot > 0 ? name.slice(0, dot) : name;
    const ext  = dot > 0 ? name.slice(dot)    : '';
    let n = 2;
    while (this.uploadedImages.some(i => i.name === `${base} (${n})${ext}`)) n++;
    return `${base} (${n})${ext}`;
  }

  removeImage(i: number) {
    const removed = this.uploadedImages[i];
    this.uploadedImages.splice(i, 1);
    if (this.imageAnalysis?.name === removed?.name) this.imageAnalysis = null;
  }

  // ── AI: clinical image analysis ────────────────────────────────────────────
  // Suggestions only. Nothing here writes to the record — the doctor copies a
  // condition into the diagnosis field explicitly, or ignores it.

  imageAnalysis: { name: string; url: string; result: ImageAnalysisResult } | null = null;
  analysingImage = '';        // name of the image currently being analysed
  imageAnalysisError = '';

  analyseImage(img: ImageItem) {
    if (!this.patient || this.analysingImage) return;
    this.analysingImage = img.name;
    this.imageAnalysisError = '';

    this.api.analyseClinicalImage({
      patientId: this.patient.id,
      imageUrl: img.url,
      imageName: img.name,
      doctorName: this.auth.getUser()?.name,
    }).subscribe({
      next: (result) => {
        this.analysingImage = '';
        if (!result.available) {
          this.imageAnalysisError = result.reason || 'Image analysis is unavailable.';
          return;
        }
        this.addedConditions.clear();
        this.imageAnalysis = { name: img.name, url: img.url, result };
      },
      error: () => {
        this.analysingImage = '';
        this.imageAnalysisError = 'Could not reach the analysis service.';
      }
    });
  }

  closeImageAnalysis() { this.imageAnalysis = null; }

  /** Conditions the doctor has accepted from this analysis, for button state. */
  addedConditions = new Set<string>();

  isConditionAdded(name: string): boolean {
    return this.addedConditions.has(name)
        || this.diagnosis.toLowerCase().includes(name.toLowerCase());
  }

  /** Doctor accepts a suggested condition — appended to the diagnosis field. */
  addConditionToDiagnosis(name: string) {
    if (!this.isConditionAdded(name)) {
      const current = this.diagnosis.trim();
      this.diagnosis = current ? `${current}, ${name}` : name;
      this.onFieldEdit();
    }
    this.addedConditions.add(name);
  }

  /** Close the analysis and jump to the field the condition was written into. */
  goToDiagnosis() {
    this.closeImageAnalysis();
    this.activeTab = 'clinical';
    setTimeout(() => {
      const field = document.getElementById('cs-diagnosis') as HTMLInputElement | null;
      field?.focus();
      field?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 60);
  }

  // ── AI: clinical summary ───────────────────────────────────────────────────

  summary: ClinicalSummaryResult | null = null;
  generatingSummary = false;
  summaryError = '';

  generateSummary() {
    if (!this.patient || this.generatingSummary) return;
    this.generatingSummary = true;
    this.summaryError = '';

    this.api.generateClinicalSummary({
      patientId: this.patient.id,
      symptoms: this.symptoms,
      vitals: { ...this.vitals } as unknown as Record<string, string>,
      diagnosis: this.diagnosis,
      notes: this.notes,
      doctorName: this.auth.getUser()?.name,
    }).subscribe({
      next: (result) => {
        this.generatingSummary = false;
        if (!result.available) {
          this.summaryError = result.reason || 'Summary generation is unavailable.';
          return;
        }
        this.summary = result;
      },
      error: () => {
        this.generatingSummary = false;
        this.summaryError = 'Could not reach the summary service.';
      }
    });
  }

  closeSummary() { this.summary = null; }

  /** Doctor accepts the draft notes — appended below anything already written. */
  useRecommendedNotes() {
    if (!this.summary?.recommendedNotes) return;
    const existing = this.notes.trim();
    this.notes = existing
      ? `${existing}\n\n${this.summary.recommendedNotes}`
      : this.summary.recommendedNotes;
    this.closeSummary();
  }

  // ── Annotation ────────────────────────────────────────

  openAnnotator(img: ImageItem, i: number) {
    this.annotating = { img, idx: i };
    this.annotTool = 'pencil';
    this.undoStack = [];
    this.textInputActive = false;
    this.annotIsDrawing = false;
    setTimeout(() => this.initAnnotCanvas(img.url), 80);
  }

  private initAnnotCanvas(url: string) {
    const bgCanvas  = document.getElementById('annot-bg')   as HTMLCanvasElement;
    const drawCanvas = document.getElementById('annot-draw') as HTMLCanvasElement;
    if (!bgCanvas || !drawCanvas) return;
    this.drawCanvas = drawCanvas;

    const img = new Image();
    img.onload = () => {
      const maxW = Math.min(window.innerWidth  * 0.82, 1100);
      const maxH = window.innerHeight * 0.68;
      let w = img.naturalWidth, h = img.naturalHeight;
      const scale = Math.min(maxW / w, maxH / h, 1);
      w = Math.round(w * scale);
      h = Math.round(h * scale);

      [bgCanvas, drawCanvas].forEach(c => { c.width = w; c.height = h; });
      bgCanvas.getContext('2d')!.drawImage(img, 0, 0, w, h);
      this.drawCtx = drawCanvas.getContext('2d')!;
      this.drawCtx.clearRect(0, 0, w, h);
    };
    img.src = url;
  }

  private getCanvasXY(e: MouseEvent | Touch): { x: number; y: number } {
    if (!this.drawCanvas) return { x: 0, y: 0 };
    const r = this.drawCanvas.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  }

  onAnnotMouseDown(e: MouseEvent) {
    if (!this.drawCtx || !this.drawCanvas) return;
    const { x, y } = this.getCanvasXY(e);

    if (this.annotTool === 'text') {
      this.textX = x; this.textY = y;
      this.textValue = '';
      this.textInputActive = true;
      setTimeout(() => (document.getElementById('annot-text-input') as HTMLInputElement)?.focus(), 20);
      return;
    }

    this.undoStack.push(this.drawCtx.getImageData(0, 0, this.drawCanvas.width, this.drawCanvas.height));
    if (this.undoStack.length > 25) this.undoStack.shift();

    this.annotIsDrawing = true;
    this.annotLastX = x;
    this.annotLastY = y;
    this.drawCtx.beginPath();
    this.drawCtx.moveTo(x, y);
  }

  onAnnotMouseMove(e: MouseEvent) {
    if (!this.annotIsDrawing || !this.drawCtx || !this.drawCanvas) return;
    const { x, y } = this.getCanvasXY(e);

    if (this.annotTool === 'eraser') {
      const sz = this.annotSize * 8;
      this.drawCtx.clearRect(x - sz / 2, y - sz / 2, sz, sz);
    } else {
      this.drawCtx.strokeStyle = this.annotColor;
      this.drawCtx.lineWidth   = this.annotSize;
      this.drawCtx.lineCap     = 'round';
      this.drawCtx.lineJoin    = 'round';
      const mx = (x + this.annotLastX) / 2;
      const my = (y + this.annotLastY) / 2;
      this.drawCtx.quadraticCurveTo(this.annotLastX, this.annotLastY, mx, my);
      this.drawCtx.stroke();
      this.drawCtx.beginPath();
      this.drawCtx.moveTo(mx, my);
    }
    this.annotLastX = x;
    this.annotLastY = y;
  }

  onAnnotMouseUp() { this.annotIsDrawing = false; }

  onAnnotTouchStart(e: TouchEvent) {
    e.preventDefault();
    this.onAnnotMouseDown(e.touches[0] as unknown as MouseEvent);
  }
  onAnnotTouchMove(e: TouchEvent) {
    e.preventDefault();
    this.onAnnotMouseMove(e.touches[0] as unknown as MouseEvent);
  }
  onAnnotTouchEnd(e: TouchEvent) { e.preventDefault(); this.onAnnotMouseUp(); }

  commitText() {
    if (!this.drawCtx || !this.drawCanvas) { this.textInputActive = false; return; }
    if (this.textValue.trim()) {
      this.undoStack.push(this.drawCtx.getImageData(0, 0, this.drawCanvas.width, this.drawCanvas.height));
      const fontSize = Math.max(12, this.annotSize * 5);
      this.drawCtx.font      = `bold ${fontSize}px sans-serif`;
      this.drawCtx.fillStyle = this.annotColor;
      this.drawCtx.fillText(this.textValue, this.textX, this.textY + fontSize);
    }
    this.textInputActive = false;
    this.textValue = '';
  }

  undoAnnot() {
    if (!this.undoStack.length || !this.drawCtx || !this.drawCanvas) return;
    this.drawCtx.putImageData(this.undoStack.pop()!, 0, 0);
  }

  clearAnnot() {
    if (!this.drawCtx || !this.drawCanvas) return;
    this.undoStack.push(this.drawCtx.getImageData(0, 0, this.drawCanvas.width, this.drawCanvas.height));
    this.drawCtx.clearRect(0, 0, this.drawCanvas.width, this.drawCanvas.height);
  }

  saveAnnotation() {
    if (!this.drawCanvas || !this.annotating) return;
    const bgCanvas = document.getElementById('annot-bg') as HTMLCanvasElement;
    if (!bgCanvas) return;

    const merged = document.createElement('canvas');
    merged.width  = bgCanvas.width;
    merged.height = bgCanvas.height;
    const mCtx = merged.getContext('2d')!;
    mCtx.drawImage(bgCanvas,     0, 0);
    mCtx.drawImage(this.drawCanvas, 0, 0);

    this.uploadedImages[this.annotating.idx] = {
      name:       this.annotating.img.name,
      url:        merged.toDataURL('image/jpeg', 0.92),
      annotated:  true
    };
    this.closeAnnotator();
  }

  closeAnnotator() {
    this.annotating     = null;
    this.drawCtx        = null;
    this.drawCanvas     = null;
    this.undoStack      = [];
    this.annotIsDrawing = false;
    this.textInputActive = false;
  }

  private compressImage(url: string, maxW = 800): Promise<string> {
    return new Promise(resolve => {
      const img = new Image();
      img.onload = () => {
        const c = document.createElement('canvas');
        let w = img.naturalWidth, h = img.naturalHeight;
        if (w > maxW) { h = Math.round(h * maxW / w); w = maxW; }
        c.width = w; c.height = h;
        c.getContext('2d')!.drawImage(img, 0, 0, w, h);
        resolve(c.toDataURL('image/jpeg', 0.78));
      };
      img.src = url;
    });
  }

  private buildMedHistory(extra?: object): string {
    return JSON.stringify({
      symptoms: this.symptoms,
      vitals: this.vitals,
      diagnosis: this.diagnosis,
      notes: this.notes,
      ...(this.jrNotes ? { jrNotes: this.jrNotes } : {}),
      ...extra,
    });
  }

  saveDraft() {
    if (!this.patient || this.isSaving) return;
    this.isSaving = true;
    this.draftError = '';
    this.savedDraft = false;
    this.api.updatePatient(this.patient.id, { medicalHistory: this.buildMedHistory() }).subscribe({
      next: () => { this.isSaving = false; this.savedDraft = true; setTimeout(() => this.savedDraft = false, 2500); },
      error: () => { this.isSaving = false; this.draftError = 'Could not save draft. Please check your connection and try again.'; }
    });
  }

  async completeConsultation() {
    if (!this.patient) return;
    if (!this.validateClinical()) return;   // symptoms + vitals are mandatory
    this.isCompleting = true;
    const doctorName = this.auth.getUser()?.name ?? '';
    const chief = this.symptoms.join(', ') || this.diagnosis || 'General Consultation';

    const images = this.uploadedImages.length
      ? await Promise.all(this.uploadedImages.map(async img => ({
          name: img.name,
          url:  await this.compressImage(img.url),
          annotated: img.annotated ?? false
        })))
      : undefined;

    this.api.updatePatient(this.patient.id, {
      medicalHistory: this.buildMedHistory({ completedAt: new Date().toISOString(), ...(images ? { images } : {}) })
    }).pipe(
      switchMap(() => this.api.createConsultation({ patientId: this.patient!.id, chiefComplaint: chief, doctorName }))
    ).subscribe({
      next: () => { this.isCompleting = false; this.router.navigate(['/doctor-queue']); },
      error: () => { this.isCompleting = false; }
    });
  }

  back() { this.router.navigate(['/doctor-queue']); }
}
