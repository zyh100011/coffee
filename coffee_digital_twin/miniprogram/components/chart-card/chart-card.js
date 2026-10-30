const { displayUnit } = require('../../utils/format');
Component({
  data: { unitText: '' },
  observers: { unit(unit) { this.setData({unitText: displayUnit(unit)}); } },
  properties: {
    title: String,
    unit: String,
    items: {
      type: Array,
      value: []
    }
  }
});
