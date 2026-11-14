import { ModulesComponent } from './modules.component';

describe('ModulesComponent', () => {
  it('lists the complete set of planned business modules by domain', () => {
    const component = new ModulesComponent();
    const allModules = component.groups.flatMap((group) => group.modules);
    expect(component.groups.length).toBe(6);
    expect(allModules.length).toBe(22);
    expect(new Set(allModules.map((module) => module.code)).size).toBe(22);
    expect(allModules.find((module) => module.code === 'payroll')?.route).toBe('/payroll');
    expect(allModules.find((module) => module.code === 'ai-command')?.route).toBe('/ai');
  });
});
