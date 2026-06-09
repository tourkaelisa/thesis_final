import { CommonModule } from '@angular/common';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { Router } from '@angular/router';
import { AuthService, CurrentUser } from '../../services/auth';

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
    email: ['', [Validators.required, Validators.email]],
    phone: ['', [Validators.pattern(/^[0-9+\s-]{10,16}$/)]],
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

    this.http.post<CurrentUser>('http://localhost:8000/api/register', payload).subscribe({
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
