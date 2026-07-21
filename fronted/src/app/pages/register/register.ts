import { CommonModule } from '@angular/common';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { AbstractControl, FormBuilder, ReactiveFormsModule, ValidationErrors, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { Router } from '@angular/router';
import { AuthService, CurrentUser } from '../../services/auth';

// Ίδιο regex με τον server (security.py): απαιτεί domain με TLD ≥ 2 γραμμάτων.
// Απορρίπτει π.χ. "a@a" που το Validators.email δέχεται.
const EMAIL_PATTERN = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,}$/;

// Προαιρετικό πεδίο: αν είναι κενό περνάει. Αλλιώς επιτρέπει μόνο ψηφία/+/κενά/παύλες
// και απαιτεί 10-15 *ψηφία* (10 για ελληνικά, έως 15 για διεθνή με κωδικό χώρας).
function phoneValidator(control: AbstractControl): ValidationErrors | null {
  const value = (control.value ?? '').trim();
  if (!value) return null;
  if (!/^[0-9+\s-]+$/.test(value)) return { phone: true };
  const digits = value.replace(/\D/g, '');
  return digits.length >= 10 && digits.length <= 15 ? null : { phone: true };
}

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatButtonModule,
    MatCheckboxModule,
    MatFormFieldModule,
    MatInputModule
  ],
  templateUrl: './register.html',
  styleUrls: ['./register.css']
})
export class Register {
  private fb = inject(FormBuilder);
  private http = inject(HttpClient);
  private router = inject(Router);
  private auth = inject(AuthService);

  submitted = signal(false);
  isSubmitting = signal(false);
  successMessage = signal('');
  errorMessage = signal('');

  registerForm = this.fb.group({
    firstName: ['', [Validators.required, Validators.minLength(2)]],
    lastName: ['', [Validators.required, Validators.minLength(2)]],
    email: ['', [Validators.required, Validators.email, Validators.pattern(EMAIL_PATTERN)]],
    phone: ['', [phoneValidator]],
    password: ['', [Validators.required, Validators.minLength(8)]],
    confirmPassword: ['', [Validators.required]],
    terms: [false, [Validators.requiredTrue]]
  });

  get passwordsDoNotMatch(): boolean {
    const password = this.registerForm.controls.password.value;
    const confirmPassword = this.registerForm.controls.confirmPassword.value;

    return Boolean(confirmPassword && password !== confirmPassword);
  }

  onSubmit(): void {
    this.submitted.set(true);
    this.successMessage.set('');
    this.errorMessage.set('');

    if (this.registerForm.invalid || this.passwordsDoNotMatch) {
      this.registerForm.markAllAsTouched();
      return;
    }

    const { confirmPassword, ...payload } = this.registerForm.getRawValue();
    this.isSubmitting.set(true);

    this.http.post<CurrentUser>('/api/register', payload).subscribe({
      next: (user) => {
        this.auth.setUser(user);
        this.successMessage.set('Ο λογαριασμός δημιουργήθηκε με επιτυχία.');
        this.registerForm.reset({ terms: false });
        this.submitted.set(false);
        this.isSubmitting.set(false);
        this.router.navigateByUrl('/');
      },
      error: (error: HttpErrorResponse) => {
        this.errorMessage.set(error.status === 409
          ? 'Υπάρχει ήδη λογαριασμός με αυτό το email.'
          : 'Δεν ήταν δυνατή η δημιουργία λογαριασμού. Δοκίμασε ξανά.');
        this.isSubmitting.set(false);
      }
    });
  }
}
