import React from 'react';
import {Composition} from 'remotion';
import {Reel} from './Reel';
import {duration} from './timeline';
import type {ReelProps} from './types';

const placeholder: ReelProps = {
	assetBase: '',
	mediaBase: '',
	reel: {
		id: 'demo', project: 'demo', variant: null, title: 'demo', width: 1080, height: 1920, fps: 30, sources: {}, clips: [],
		style: {preset: 'impact', font: 'Montserrat', weight: 900, uppercase: true, size: 72, color: '#FFFFFF',
			highlight: '#FFD400', stroke: '#000000', strokeWidth: 12, position: 0.68, maxWords: 3, pop: true},
		zoom: {auto: true, strength: 1.14, push: 0.03, overrides: {}},
		banner: {enabled: false, text: '', start: 0, end: null}, flash: {enabled: true}, progress: {enabled: false},
	},
};

export const Root: React.FC = () => (
	<Composition
		id="Reel"
		component={Reel}
		defaultProps={placeholder}
		durationInFrames={60}
		fps={30}
		width={1080}
		height={1920}
		calculateMetadata={({props}) => ({
			durationInFrames: Math.max(1, Math.round(duration(props.reel) * props.reel.fps)),
			fps: props.reel.fps,
			width: props.reel.width,
			height: props.reel.height,
		})}
	/>
);
