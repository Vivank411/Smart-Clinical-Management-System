import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { switchMap } from 'rxjs/operators';
import { ApiService, ApiPatient } from '../../services/api.service';
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
    const files = (e.target as HTMLInputElement).files;
    if (!files) return;
    for (const f of Array.from(files)) {
      const reader = new FileReader();
      reader.onload = ev => { this.uploadedImages.push({ name: f.name, url: ev.target!.result as string }); };
      reader.readAsDataURL(f);
    }
    (e.target as HTMLInputElement).value = '';
  }

  removeImage(i: number) { this.uploadedImages.splice(i, 1); }

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
