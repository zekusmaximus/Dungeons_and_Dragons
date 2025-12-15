import { render, screen, fireEvent } from '@testing-library/react';
import SchemaForm from '../SchemaForm';

const mockSchema = {
  properties: {
    name: { type: 'string' },
    age: { type: 'integer' },
    active: { type: 'boolean' },
    type: { type: 'string', enum: ['A', 'B'] },
  },
  required: ['name'],
};

const mockData = { name: 'Test', age: 25 };

test('renders form fields', () => {
  render(
    <SchemaForm
      schema={mockSchema}
      data={mockData}
      onChange={() => {}}
      onSubmit={() => {}}
      errors={[]}
    />
  );
  expect(screen.getByDisplayValue('Test')).toBeInTheDocument();
  expect(screen.getByDisplayValue('25')).toBeInTheDocument();
});

test('shows errors', () => {
  render(
    <SchemaForm
      schema={mockSchema}
      data={mockData}
      onChange={() => {}}
      onSubmit={() => {}}
      errors={['Name is required']}
    />
  );
  expect(screen.getByText('Name is required')).toBeInTheDocument();
});