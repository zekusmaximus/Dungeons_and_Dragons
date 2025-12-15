import React, { useState } from 'react';

interface SchemaProperty {
  type: string;
  enum?: string[];
  // add more as needed
}

interface Schema {
  properties: Record<string, SchemaProperty>;
  required?: string[];
}

interface SchemaFormProps {
  schema: Schema;
  data: Record<string, any>;
  onChange: (data: Record<string, any>) => void;
  onSubmit: () => void;
  errors: string[];
}

const SchemaForm: React.FC<SchemaFormProps> = ({ schema, data, onChange, onSubmit, errors }) => {
  const handleFieldChange = (key: string, value: any) => {
    onChange({ ...data, [key]: value });
  };

  const renderField = (key: string, prop: SchemaProperty) => {
    const value = data[key] || '';
    const isRequired = schema.required?.includes(key);

    if (prop.enum) {
      return (
        <select
          value={value}
          onChange={(e) => handleFieldChange(key, e.target.value)}
          required={isRequired}
        >
          <option value="">Select...</option>
          {prop.enum.map((opt) => (
            <option key={opt} value={opt}>{opt}</option>
          ))}
        </select>
      );
    }

    switch (prop.type) {
      case 'string':
        return (
          <input
            type="text"
            value={value}
            onChange={(e) => handleFieldChange(key, e.target.value)}
            required={isRequired}
          />
        );
      case 'integer':
        return (
          <input
            type="number"
            value={value}
            onChange={(e) => handleFieldChange(key, parseInt(e.target.value))}
            required={isRequired}
          />
        );
      case 'boolean':
        return (
          <input
            type="checkbox"
            checked={value}
            onChange={(e) => handleFieldChange(key, e.target.checked)}
          />
        );
      default:
        return <div>Unsupported type: {prop.type}</div>;
    }
  };

  return (
    <form onSubmit={(e) => { e.preventDefault(); onSubmit(); }}>
      {Object.entries(schema.properties).map(([key, prop]) => (
        <div key={key}>
          <label>{key}:</label>
          {renderField(key, prop)}
        </div>
      ))}
      {errors.length > 0 && (
        <div style={{ color: 'red' }}>
          {errors.map((err, i) => <div key={i}>{err}</div>)}
        </div>
      )}
      <button type="submit">Submit</button>
    </form>
  );
};

export default SchemaForm;