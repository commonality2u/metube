import { Component, Input, ViewChild, ElementRef, Output, EventEmitter } from '@angular/core';

interface Checkable {
  checked: boolean;
}

@Component({
  selector: 'app-master-checkbox',
  template: `
  <div class="form-check">
    <input type="checkbox" class="form-check-input" id="{{id}}-select-all" #masterCheckbox [checked]="selected" (change)="clicked()">
    <label class="form-check-label" for="{{id}}-select-all"></label>
  </div>
`
})
export class MasterCheckboxComponent {
  @Input() id: string;
  @Input() list: Map<string, Checkable>;
  @Output() changed = new EventEmitter<number>();

  @ViewChild('masterCheckbox') masterCheckbox: ElementRef;
  selected = false;

  clicked() {
    this.selected = !this.selected;
    for (const item of this.list.values()) {
      item.checked = this.selected;
    }
    this.selectionChanged();
  }

  selectionChanged() {
    if (!this.masterCheckbox) {
      return;
    }
    let checked = 0;
    for (const item of this.list.values()) {
      if (item.checked) {
        checked++;
      }
    }
    this.selected = checked > 0 && checked === this.list.size;
    this.masterCheckbox.nativeElement.indeterminate = checked > 0 && checked < this.list.size;
    this.changed.emit(checked);
  }
}

@Component({
  selector: 'app-slave-checkbox',
  template: `
  <div class="form-check">
    <input type="checkbox" class="form-check-input" id="{{master.id}}-{{id}}-select" [checked]="checkable.checked" (change)="toggleChecked()">
    <label class="form-check-label" for="{{master.id}}-{{id}}-select"></label>
  </div>
`
})
export class SlaveCheckboxComponent {
  @Input() id: string;
  @Input() master: MasterCheckboxComponent;
  @Input() checkable: Checkable;

  toggleChecked() {
    this.checkable.checked = !this.checkable.checked;
    this.master.selectionChanged();
  }
}
