import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { AppComponent } from './app.component';

describe('AppComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AppComponent],
      providers: [provideRouter([]), provideHttpClient()],
    }).compileComponents();
  });

  it('creates the application shell with the intro screen visible first', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    expect(fixture.componentInstance).toBeTruthy();
    expect(fixture.componentInstance.showIntro).toBeTrue();
    expect(fixture.nativeElement.textContent).toContain('AETHEREON');
    expect(fixture.nativeElement.textContent).toContain('INTELIGENCIA EMPRESARIAL');
  });
});
